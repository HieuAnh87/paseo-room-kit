import type { PluginClientContext } from "@getpaseo/plugin/client";
import { FlowSurface } from "./client/flow.tsx";

export default function contribute(client: PluginClientContext) {
  const removeSurface = client.addSurface("room-flow", FlowSurface);
  const removeSidebar = client.addSidebarItem({
    id: "room-flow",
    title: "Room Flow",
    icon: "Activity",
    surface: "room-flow",
  });
  return () => {
    removeSidebar();
    removeSurface();
  };
}
