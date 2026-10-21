import type { PluginServerContext } from "@getpaseo/plugin/server";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, lstatSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { promisify } from "node:util";

type Result = {state?: string};
type Services = {
  run(args: string[]): Promise<Result>;
  publish(): void;
  unpublish(): void;
  delay(milliseconds: number): Promise<void>;
};

function localServices(): Services {
  const directory = dirname(process.env.ROOM_GUARD_LEASES_PATH ?? process.env.PASEO_ROOM_LEASES_PATH ?? join(homedir(), ".config/room-workflow/lead-leases.json"));
  const healthPath = join(directory, "callback-relay.json");
  const bin = join(homedir(), ".local/bin");
  const execute = promisify(execFile);
  const environment: NodeJS.ProcessEnv = {...process.env, ROOM_CALLBACK_SERVICE: "1"};
  delete environment.PASEO_ROOM_ROLE;
  return {
    async run(args) {
      const {stdout} = await execute(join(bin, "paseo-room-workflow"), args, {
        env: environment, timeout: 24000, maxBuffer: 1024 * 1024,
      });
      return JSON.parse(stdout) as Result;
    },
    publish() {
      mkdirSync(directory, {recursive: true, mode: 0o700});
      const info = lstatSync(directory);
      if (!info.isDirectory() || info.uid !== process.getuid?.() || (info.mode & 0o022)) {
        throw new Error("Callback health requires an owner-only writable directory");
      }
      const temporary = `${healthPath}.${process.pid}.tmp`;
      writeFileSync(temporary, JSON.stringify({
        version: 1, pid: process.pid, heartbeat: Date.now()/1000,
        proxyDigest: createHash("sha256").update(readFileSync(join(bin, "paseo-room-mcp"))).digest("hex"),
      }), {mode: 0o600, flag: "wx"});
      renameSync(temporary, healthPath);
    },
    unpublish() {
      try {
        if (JSON.parse(readFileSync(healthPath, "utf8")).pid === process.pid) unlinkSync(healthPath);
      } catch { /* A missing heartbeat is already fail-closed. */ }
    },
    delay: (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  };
}

export function startRelay(server: PluginServerContext, services: Services = localServices()) {
  let closed = false;
  let ready = false;
  const remove = server.on("agent.turn_ended", async ({agent}) => {
    // The event snapshot has no labels. The owner CLI validates canonical
    // labels, native binding, epoch and assignment; it chooses the recipient.
    const provider = agent.provider.split("/")[0] ?? "";
    const uiProvider = provider === "antigravity-cli" || provider === "claude-ui";
    if ((!uiProvider && !/(?:-peer|-reviewer)$/.test(provider)) || !/^[0-9a-f-]{36}$/i.test(agent.id)) return;
    for (const delay of [100, 500, 1500]) {
      await services.delay(delay);
      if (closed) return;
      const result = await services.run(["callback", "--agent-id", agent.id]);
      if (!["WAITING", "IGNORED"].includes(result.state ?? "")) return;
    }
  });
  const timer = setInterval(() => {
    if (!ready || closed) return;
    try {services.publish();}
    catch (error) {services.unpublish(); console.error("room-callback heartbeat failed", error);}
  }, 5000);
  // One bounded restart reconciliation, never a background progress poll.
  void services.run(["callback-sweep"]).then(() => {
    if (!closed) {services.publish(); ready = true;}
  }).catch((error: unknown) => {
    services.unpublish(); console.error("room-callback startup reconciliation failed", error);
  });
  return () => {
    closed = true; clearInterval(timer); remove(); services.unpublish();
  };
}
