import type { PluginHookContext } from "@getpaseo/plugin/server";
import { deriveRooms, type AgentView, type WorkspaceView } from "./derive.ts";
import { readLeases } from "./read.ts";

type Paseo = PluginHookContext["paseo"];

async function listAgents(paseo: Paseo): Promise<AgentView[]> {
  const agents: AgentView[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < 50; page++) {
    const result = await paseo.agents.list({
      filter: { includeArchived: false },
      page: cursor ? { limit: 200, cursor } : { limit: 200 },
    });
    agents.push(...result.entries.map((entry) => entry.agent as unknown as AgentView));
    if (!result.pageInfo?.hasMore) return agents;
    if (!result.pageInfo.nextCursor || result.pageInfo.nextCursor === cursor) break;
    cursor = result.pageInfo.nextCursor;
  }
  throw new Error("Paseo agent directory is incomplete; Flow cannot present a safe snapshot");
}

async function listWorkspaces(paseo: Paseo): Promise<WorkspaceView[]> {
  const workspaces: WorkspaceView[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < 50; page++) {
    const result = await paseo.workspaces.list({ page: cursor ? { limit: 200, cursor } : { limit: 200 } });
    workspaces.push(...result.entries.map((entry) => entry as unknown as WorkspaceView));
    if (!result.pageInfo?.hasMore) return workspaces;
    if (!result.pageInfo.nextCursor || result.pageInfo.nextCursor === cursor) break;
    cursor = result.pageInfo.nextCursor;
  }
  throw new Error("Paseo workspace directory is incomplete; Flow cannot present a safe snapshot");
}

export async function snapshot(paseo: Paseo) {
  const [{ source, leases }, agents, workspaces] = await Promise.all([
    readLeases(), listAgents(paseo), listWorkspaces(paseo),
  ]);
  return { generatedAt: new Date().toISOString(), leaseSource: source, rooms: deriveRooms(leases, agents, workspaces) };
}
