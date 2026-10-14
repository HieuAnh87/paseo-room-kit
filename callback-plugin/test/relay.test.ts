import { test } from "node:test";
import assert from "node:assert/strict";
import type { PluginServerContext } from "@getpaseo/plugin/server";
import { startRelay } from "../server/relay.ts";
const peerId = ["1".repeat(8), "1".repeat(4), "1".repeat(4), "1".repeat(4), "1".repeat(12)].join("-");
const leadId = peerId.replaceAll("1", "2");

test("registers real lifecycle name, forwards only agent identity and cleans up", async () => {
  let handler: (event: {agent: {id: string; provider: string}}) => Promise<void> = async () => {};
  const calls: string[][] = [];
  let health = 0, removed = 0, stopped = false;
  const server = {on(name: string, fn: typeof handler) {
    assert.equal(name, "agent.turn_ended"); handler = fn; return () => {removed++;};
  }} as unknown as PluginServerContext;
  const cleanup = startRelay(server, {
    run: async (args) => {calls.push(args); return {state: "DELIVERED"};},
    publish: () => {health++;}, unpublish: () => {stopped = true;},
    delay: async () => {},
  });
  await handler({agent: {id: peerId, provider: "codex-peer"}});
  await handler({agent: {id: leadId, provider: "codex-lead"}});
  assert.deepEqual(calls, [["callback-sweep"], ["callback", "--agent-id", peerId]]);
  assert.ok(health > 0); cleanup(); assert.equal(removed, 1); assert.equal(stopped, true);
});

test("bounded event retry covers creation race but never retries uncertain delivery", async () => {
  let handler: (event: {agent: {id: string; provider: string}}) => Promise<void> = async () => {};
  let attempts = 0;
  const server = {on(_name: string, fn: typeof handler) {handler=fn; return () => {};}} as unknown as PluginServerContext;
  const cleanup = startRelay(server, {
    run: async (args) => args[0] === "callback-sweep" ? {} : (++attempts < 2 ? {state:"IGNORED"} : {state:"UNCERTAIN"}),
    publish: () => {}, unpublish: () => {}, delay: async () => {},
  });
  await handler({agent: {id:peerId, provider:"claude-reviewer"}});
  assert.equal(attempts, 2); cleanup();
});

for (const provider of ["antigravity-cli", "claude-ui"]) {
  test(`UI lifecycle ${provider} reaches canonical assignment validation`, async () => {
    let handler: (event: {agent: {id: string; provider: string}}) => Promise<void> = async () => {};
    const calls: string[][] = [];
    const server = {on(_name: string, fn: typeof handler) {handler = fn; return () => {};}} as unknown as PluginServerContext;
    const cleanup = startRelay(server, {
      run: async (args) => {calls.push(args); return {state: "DELIVERED"};},
      publish: () => {}, unpublish: () => {}, delay: async () => {},
    });
    await handler({agent: {id: peerId, provider}});
    await handler({agent: {id: leadId, provider: "claude-lead"}});
    await handler({agent: {id: "invalid", provider}});
    assert.deepEqual(calls, [["callback-sweep"], ["callback", "--agent-id", peerId]]);
    cleanup();
  });
}
