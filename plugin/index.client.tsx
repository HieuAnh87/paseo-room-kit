import type { PluginClientContext } from "@getpaseo/plugin/client";
import { FlowSurface } from "./client/flow.tsx";
import { ModelsPreviewSurface } from "./client/models-preview.tsx";

export default function contribute(client: PluginClientContext) {
  const removeSurface = client.addSurface("room-flow", FlowSurface);
  const removeSidebar = client.addSidebarItem({
    id: "room-flow",
    title: "Room Flow",
    icon: "Activity",
    surface: "room-flow",
  });
  const removeModels = client.addSurface("model-effort-preview", ModelsPreviewSurface);
  const removeModelsItem = client.addSidebarItem({
    id: "model-effort-preview",
    title: "Models · preview",
    icon: "SlidersHorizontal",
    surface: "model-effort-preview",
  });
  return () => {
    removeModelsItem();
    removeModels();
    removeSidebar();
    removeSurface();
  };
}
