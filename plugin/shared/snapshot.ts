import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";

const seat = z.object({
  id: z.string(),
  title: z.string(),
  role: z.string(),
  status: z.string(),
  taskState: z.string(),
  assignmentId: z.string().nullable(),
  pendingPermissions: z.number().int().nonnegative(),
});

const signal = z.object({
  code: z.string(),
  level: z.enum(["info", "attention", "critical"]),
  message: z.string(),
  seatId: z.string().nullable(),
});

const ask = z.object({
  id: z.string(),
  question: z.string(),
  senderAgentId: z.string(),
  recipientAgentId: z.string(),
  createdAt: z.string(),
  kind: z.string().nullable(),
  resolution: z.object({ outcome: z.string(), decision: z.string(), evidence: z.string(),
    nextAction: z.string(), owner: z.string().nullable(), checkpoint: z.string().nullable() }).nullable(),
});

const room = z.object({
  workspaceId: z.string(),
  workspaceName: z.string(),
  leaseState: z.string(),
  decisionState: z.string(),
  humanDecision: z.enum(["ACCEPTED", "ABANDONED"]).nullable(),
  authorityMode: z.string(),
  workEpoch: z.number().int().positive(),
  revision: z.number().int().positive(),
  lead: seat.nullable(),
  supervisor: seat.nullable(),
  peers: z.array(seat),
  reportCount: z.number().int().nonnegative(),
  candidatePresent: z.boolean(),
  openAsks: z.array(ask),
  steering: z.array(z.object({ grantId: z.string(), peerAgentId: z.string(), state: z.string() })),
  signals: z.array(signal),
});

const snapshotSchema = z.object({
    generatedAt: z.string(),
    leaseSource: z.enum(["present", "missing"]),
    rooms: z.array(room),
});

export const snapshotRpc = defineRpc({
  name: "room-flow.snapshot",
  input: z.object({}),
  output: snapshotSchema,
});

export type RoomSnapshot = z.infer<typeof snapshotSchema>;
export type Room = z.infer<typeof room>;
export type Seat = z.infer<typeof seat>;
export type Signal = z.infer<typeof signal>;
export type Ask = z.infer<typeof ask>;
