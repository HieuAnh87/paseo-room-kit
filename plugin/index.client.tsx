import type { PluginClientContext, PluginSidebarItemProps } from "@getpaseo/plugin/client";
import { SidebarRow } from "@getpaseo/plugin/client/ui";
import { FlowSurface } from "./client/flow.tsx";
import { ModelsPreviewSurface } from "./client/models-preview.tsx";

function RoomFlowSidebar({ currentScreen, openScreen }: PluginSidebarItemProps) {
  return (
    <>
      <SidebarRow
        id="overview"
        icon="Activity"
        label="Room Flow"
        active={currentScreen?.screenId === "room-flow"}
        onPress={() => openScreen({ screenId: "room-flow" })}
      />
      <SidebarRow
        id="models"
        icon="SlidersHorizontal"
        label="Model & effort"
        active={currentScreen?.screenId === "model-effort-preview"}
        onPress={() => openScreen({ screenId: "model-effort-preview" })}
      />
    </>
  );
}

export default function contribute(client: PluginClientContext) {
  const removeFlow = client.addScreen({ id: "room-flow", title: "Room Flow", Component: FlowSurface });
  const removeModels = client.addScreen({
    id: "model-effort-preview",
    title: "Room Flow · Model & effort",
    Component: ModelsPreviewSurface,
  });
  const removeSidebar = client.addSidebarHeaderItem({
    id: "room-flow",
    title: "Room Flow",
    Component: RoomFlowSidebar,
  });
  return () => {
    removeSidebar();
    removeModels();
    removeFlow();
  };
}
