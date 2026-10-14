import type { Room, Seat, Signal } from "../shared/snapshot.ts";
import type { Lease } from "./read.ts";

export type AgentView = {
  id: string;
  workspaceId?: string | null;
  title?: string | null;
  status?: string | null;
  archivedAt?: string | null;
  labels?: Record<string, string> | null;
  pendingPermissions?: unknown[] | null;
};

export type WorkspaceView = {
  id: string;
  name?: string | null;
  archivingAt?: string | null;
  archivedAt?: string | null;
};

function asSeat(agent: AgentView, role: string): Seat {
  const labels = agent.labels ?? {};
  return {
    id: agent.id,
    title: agent.title?.trim() || `${role} ${agent.id.slice(0, 8)}`,
    role,
    status: agent.status ?? "unknown",
    taskState: labels.task_state ?? "unknown",
    assignmentId: labels.assignment_id ?? null,
    pendingPermissions: agent.pendingPermissions?.length ?? 0,
  };
}

function add(signals: Signal[], code: string, level: Signal["level"], message: string, seatId: string | null = null): void {
  signals.push({ code, level, message, seatId });
}

export function deriveRooms(leases: Lease[], agents: AgentView[], workspaces: WorkspaceView[]): Room[] {
  const byAgent = new Map(agents.map((agent) => [agent.id, agent]));
  const byWorkspace = new Map(workspaces.map((workspace) => [workspace.id, workspace]));
  return leases.map((lease) => {
    const workspace = byWorkspace.get(lease.workspaceId);
    const leadAgent = lease.leadAgentId ? byAgent.get(lease.leadAgentId) : undefined;
    const supervisorAgent = lease.supervisorAgentId ? byAgent.get(lease.supervisorAgentId) : undefined;
    const lead = leadAgent ? asSeat(leadAgent, "Lead") : null;
    const supervisor = supervisorAgent ? asSeat(supervisorAgent, "Supervisor") : null;
    const peers = agents.filter((agent) =>
      !agent.archivedAt && agent.workspaceId === lease.workspaceId
      && agent.labels?.role === "peer"
      && agent.labels["paseo.parent-agent-id"] === lease.leadAgentId
      && agent.labels.room_kind === "managed_slp"
    );
    const signals: Signal[] = [];

    if (lease.state === "active" && (!workspace || workspace.archivingAt || workspace.archivedAt)) {
      add(signals, "workspace-unavailable", "critical", "Active lease has no active Paseo workspace. Check authority before acting.");
    }
    if (lease.state === "active" && (!leadAgent || leadAgent.workspaceId !== lease.workspaceId || leadAgent.archivedAt)) {
      add(signals, "lead-unavailable", "critical", "Active lease does not match a live Lead in this workspace.", lease.leadAgentId);
    }
    if (lease.state === "active" && lease.supervisorAgentId && !supervisorAgent) {
      add(signals, "observer-unavailable", "attention", "Bound Supervisor is not in the active Paseo agent list.", lease.supervisorAgentId);
    }
    if (lease.state === "active" && ["HANDBACK_SENDING", "REOPEN_SENDING", "ARCHIVE_SENDING"].includes(lease.decisionState)) {
      add(signals, "delivery-uncertain", "critical", "Delivery is in an uncertain sending state; owner resolution may be required.");
    } else if (lease.decisionState === "HANDBACK_READY" && lease.state === "active") {
      if (lease.humanDecision) {
        add(signals, "human-decision-recorded", "attention", `Human marked this evidence ${lease.humanDecision}; verify the current candidate and decision queue before archive.`);
      } else {
        add(signals, "human-decision", "attention", "Lead handback is ready for Human review; check the decision queue.");
      }
    }
    if (lease.state === "active" && lease.openAsks.length > 0) {
      add(signals, "open-asks", "attention", `${lease.openAsks.length} question(s) are awaiting an answer.`);
    }
    if (lease.state === "active") {
      for (const ask of lease.openAsks.filter((ask) => ask.kind === "REOPEN_REQUEST")) {
        add(signals, "reopen-resolution", "attention", ask.resolution
          ? `Reopen request has ${ask.resolution.outcome}: ${ask.resolution.nextAction}`
          : "A Peer challenged a premise; Lead disposition is still pending.", ask.senderAgentId);
      }
      for (const grant of lease.steering.filter((grant) => !["DELIVERED", "REJECTED", "CANCELLED"].includes(grant.state))) {
        add(signals, "peer-steering", ["UNCERTAIN", "NOTICE_SENDING", "PEER_SENDING"].includes(grant.state) ? "critical" : "attention",
          `Human Peer steering ${grant.grantId} is ${grant.state}; inspect delivery evidence before acting.`, grant.peerAgentId);
      }
    }
    for (const peer of peers) {
      if (lease.state !== "active") continue;
      const seat = asSeat(peer, peer.labels?.disposition === "reviewer" ? "Reviewer" : "Peer");
      const epoch = peer.labels?.work_epoch;
      if (epoch !== String(lease.workEpoch)) {
        add(signals, "peer-epoch-mismatch", "attention", "Peer belongs to a different work epoch; verify its assignment.", peer.id);
      }
      if (seat.pendingPermissions > 0) {
        add(signals, "permission-pending", "attention", "Peer has a pending Paseo permission request.", peer.id);
      }
      if (epoch === String(lease.workEpoch) && seat.status === "idle"
        && ["ASSIGNED", "REWORK"].includes(seat.taskState)
        && !lease.reportPeerIds.has(peer.id)) {
        add(signals, "peer-idle-assigned", "info", "Peer is idle with an open assignment and no recorded report. Check handback; idle does not mean done.", peer.id);
      }
    }
    return {
      workspaceId: lease.workspaceId,
      workspaceName: workspace?.name?.trim() || lease.workspaceId,
      leaseState: lease.state,
      decisionState: lease.decisionState,
      humanDecision: lease.humanDecision,
      authorityMode: lease.authorityMode,
      workEpoch: lease.workEpoch,
      revision: lease.revision,
      lead,
      supervisor,
      peers: peers.map((peer) => asSeat(peer, peer.labels?.disposition === "reviewer" ? "Reviewer" : "Peer")),
      reportCount: lease.reportCount,
      candidatePresent: lease.candidatePresent,
      openAsks: lease.openAsks,
      steering: lease.steering,
      signals,
    };
  }).sort((left, right) => {
    const rank = (state: string) => state === "active" ? 0 : state === "pending" ? 1 : 2;
    return rank(left.leaseState) - rank(right.leaseState) || left.workspaceName.localeCompare(right.workspaceName);
  });
}
