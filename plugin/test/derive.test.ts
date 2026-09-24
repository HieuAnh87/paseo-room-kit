import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { deriveRooms, type AgentView } from "../server/derive.ts";
import { parseLeases, readLeases } from "../server/read.ts";

const workspaceId = "workspace-one";
const leadId = "lead-one";
const peerId = "peer-one";

function fixture(report = false) {
  return {
    version: 2,
    leases: {
      [workspaceId]: {
        state: "active",
        room_kind: "managed_slp",
        workspace_id: workspaceId,
        lead_agent_id: leadId,
        work_epoch: 2,
        revision: 8,
        decision_state: "WORKING",
        peer_reports: report ? {
          "report-one": { report: { peerAgentId: peerId, workEpoch: 2 } },
        } : {},
      },
    },
  };
}

const agents: AgentView[] = [
  { id: leadId, workspaceId, status: "running", labels: { role: "lead", room_kind: "managed_slp", work_epoch: "2" } },
  { id: peerId, workspaceId, status: "idle", labels: {
    role: "peer", room_kind: "managed_slp", work_epoch: "2", task_state: "ASSIGNED",
    "paseo.parent-agent-id": leadId,
  } },
];
const workspaces = [{ id: workspaceId, name: "Project work" }];

test("idle assigned Peer produces only a shadow signal, never acceptance", () => {
  const [room] = deriveRooms(parseLeases(fixture()), agents, workspaces);
  assert.equal(room.leaseState, "active");
  assert.equal(room.workEpoch, 2);
  assert.equal(room.peers.length, 1);
  assert.deepEqual(room.signals.map((signal) => signal.code), ["peer-idle-assigned"]);
  assert.equal(room.signals[0]?.level, "info");
  assert.equal(room.decisionState, "WORKING");
});

test("recorded current-epoch report suppresses idle handback hint", () => {
  const [room] = deriveRooms(parseLeases(fixture(true)), agents, workspaces);
  assert.equal(room.reportCount, 1);
  assert.equal(room.signals.length, 0);
});

test("only open current-epoch asks appear in the Flow view", () => {
  const value = fixture();
  const lease = value.leases[workspaceId] as typeof value.leases[typeof workspaceId] & { room_asks?: Record<string, unknown> };
  lease.room_asks = {
    current: { ask_id: "current", question: "Who approves this?", sender_agent_id: leadId,
      recipient_agent_id: "human", work_epoch: 2, created_at: "2026-09-24T00:00:00Z", status: "OPEN" },
    old: { ask_id: "old", question: "Old scope", sender_agent_id: leadId,
      recipient_agent_id: "human", work_epoch: 1, created_at: "2026-09-23T00:00:00Z", status: "OPEN" },
  };
  const [room] = deriveRooms(parseLeases(value), agents, workspaces);
  assert.deepEqual(room.openAsks.map((ask) => ask.id), ["current"]);
  assert.ok(room.signals.some((signal) => signal.code === "open-asks"));
});

test("uncertain handback and absent Paseo authority are visible", () => {
  const value = fixture();
  value.leases[workspaceId].decision_state = "HANDBACK_SENDING";
  const [room] = deriveRooms(parseLeases(value), [], []);
  assert.deepEqual(room.signals.map((signal) => signal.code), [
    "workspace-unavailable", "lead-unavailable", "delivery-uncertain",
  ]);
  assert.ok(room.signals.every((signal) => signal.level === "critical"));
});

test("Human acceptance is shown only for matching epoch and evidence", () => {
  const value = fixture();
  const lease = value.leases[workspaceId] as typeof value.leases[typeof workspaceId] & {
    evidence_digest?: string; human_decision?: string; human_decision_epoch?: number;
    human_decision_evidence_digest?: string;
  };
  lease.decision_state = "HANDBACK_READY";
  lease.evidence_digest = "sha256:current";
  lease.human_decision = "ACCEPTED";
  lease.human_decision_epoch = 2;
  lease.human_decision_evidence_digest = "sha256:old";
  const [stale] = deriveRooms(parseLeases(value), agents, workspaces);
  assert.equal(stale.humanDecision, null);
  assert.ok(stale.signals.some((signal) => signal.code === "human-decision"));
  lease.human_decision_evidence_digest = "sha256:current";
  const [accepted] = deriveRooms(parseLeases(value), agents, workspaces);
  assert.equal(accepted.humanDecision, "ACCEPTED");
  assert.ok(accepted.signals.some((signal) => signal.code === "human-decision-recorded"));
});

test("malformed or mismatched registry fails closed", () => {
  assert.throws(() => parseLeases({ version: 3, leases: {} }), /version/);
  const value = fixture();
  value.leases[workspaceId].workspace_id = "other-workspace";
  assert.throws(() => parseLeases(value), /mismatch/);
});

test("missing lease file is explicit; invalid JSON rejects", async () => {
  const dir = await mkdtemp(join(tmpdir(), "room-flow-test-"));
  try {
    const path = join(dir, "leases.json");
    assert.deepEqual(await readLeases(path), { source: "missing", leases: [] });
    await writeFile(path, "{");
    await assert.rejects(readLeases(path), /not valid JSON/);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
