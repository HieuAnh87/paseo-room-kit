import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { Ask } from "../shared/snapshot.ts";

export type Lease = {
  workspaceId: string;
  state: string;
  decisionState: string;
  humanDecision: "ACCEPTED" | "ABANDONED" | null;
  authorityMode: string;
  workEpoch: number;
  revision: number;
  leadAgentId: string | null;
  supervisorAgentId: string | null;
  candidatePresent: boolean;
  reportPeerIds: Set<string>;
  reportCount: number;
  openAsks: Ask[];
};

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Room lease registry contains a non-object entry");
  }
  return value as Record<string, unknown>;
}

function optionalString(value: unknown, field: string): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string") throw new Error(`Room lease has invalid ${field}`);
  return value;
}

function positiveInteger(value: unknown, field: string, fallback?: number): number {
  const found = value ?? fallback;
  if (typeof found !== "number" || !Number.isInteger(found) || found < 1) {
    throw new Error(`Room lease has invalid ${field}`);
  }
  return found;
}

export function parseLeases(value: unknown): Lease[] {
  const registry = record(value);
  if (registry.version !== 1 && registry.version !== 2) {
    throw new Error("Unsupported room lease registry version");
  }
  const rawLeases = record(registry.leases);
  return Object.entries(rawLeases).flatMap(([workspaceId, raw]) => {
    if (!workspaceId) throw new Error("Room lease has an empty workspace key");
    const lease = record(raw);
    if (lease.room_kind !== undefined && lease.room_kind !== "managed_slp") return [];
    if (lease.workspace_id !== undefined && lease.workspace_id !== workspaceId) {
      throw new Error(`Room lease workspace mismatch: ${workspaceId}`);
    }
    const state = optionalString(lease.state, "state") ?? "unknown";
    const decisionState = optionalString(lease.decision_state, "decision_state") ?? "WORKING";
    const workEpoch = positiveInteger(lease.work_epoch, "work_epoch", 1);
    const humanDecision = lease.human_decision_epoch === workEpoch
      && typeof lease.evidence_digest === "string"
      && lease.human_decision_evidence_digest === lease.evidence_digest
      && (lease.human_decision === "ACCEPTED" || lease.human_decision === "ABANDONED")
      ? lease.human_decision : null;
    const reports = lease.peer_reports === undefined ? {} : record(lease.peer_reports);
    const reportPeerIds = new Set<string>();
    let reportCount = 0;
    for (const receipt of Object.values(reports)) {
      const report = record(record(receipt).report);
      if (report.workEpoch !== workEpoch) continue;
      reportCount++;
      if (typeof report.peerAgentId === "string") reportPeerIds.add(report.peerAgentId);
    }
    const rawAsks = lease.room_asks === undefined ? {} : record(lease.room_asks);
    const openAsks: Ask[] = [];
    for (const [id, value] of Object.entries(rawAsks)) {
      const ask = record(value);
      if (ask.ask_id !== id || !["OPEN", "ANSWERED"].includes(String(ask.status))
        || typeof ask.work_epoch !== "number" || !Number.isInteger(ask.work_epoch) || ask.work_epoch < 1) {
        throw new Error(`Room lease has an invalid ask: ${id}`);
      }
      if (ask.status !== "OPEN" || ask.work_epoch !== workEpoch) continue;
      for (const key of ["question", "sender_agent_id", "recipient_agent_id", "created_at"] as const) {
        if (typeof ask[key] !== "string") throw new Error(`Room lease has an invalid ask ${key}: ${id}`);
      }
      openAsks.push({
        id,
        question: ask.question as string,
        senderAgentId: ask.sender_agent_id as string,
        recipientAgentId: ask.recipient_agent_id as string,
        createdAt: ask.created_at as string,
      });
    }
    openAsks.sort((left, right) => left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id));
    return [{
      workspaceId,
      state,
      decisionState,
      humanDecision,
      authorityMode: optionalString(lease.authority_mode, "authority_mode") ?? "parented",
      workEpoch,
      revision: positiveInteger(lease.revision, "revision", 1),
      leadAgentId: optionalString(lease.lead_agent_id, "lead_agent_id"),
      supervisorAgentId: optionalString(lease.supervisor_agent_id, "supervisor_agent_id"),
      candidatePresent: typeof lease.candidate_digest === "string" && lease.candidate_digest.length > 0,
      reportPeerIds,
      reportCount,
      openAsks,
    }];
  });
}

export function leasePath(): string {
  return process.env.ROOM_GUARD_LEASES_PATH
    || process.env.PASEO_ROOM_LEASES_PATH
    || join(homedir(), ".config", "room-workflow", "lead-leases.json");
}

export async function readLeases(path = leasePath()): Promise<{ source: "present" | "missing"; leases: Lease[] }> {
  let contents: string;
  try {
    contents = await readFile(path, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return { source: "missing", leases: [] };
    throw error;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(contents) as unknown;
  } catch {
    throw new Error("Room lease registry is not valid JSON");
  }
  return { source: "present", leases: parseLeases(parsed) };
}
