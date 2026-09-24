import { useRpc, type PluginSurfaceProps } from "@getpaseo/plugin/client";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { snapshotRpc, type Room, type Seat, type Signal } from "../shared/snapshot.ts";

export function FlowSurface({ theme, layout }: PluginSurfaceProps) {
  const [showHistory, setShowHistory] = useState(false);
  const read = useRpc(snapshotRpc);
  const query = useQuery({
    queryKey: ["room-flow", "snapshot"],
    queryFn: () => read({}),
    refetchInterval: 15_000,
  });
  const styles = useMemo(() => ({
    screen: { flex: 1, backgroundColor: theme.colors.surface0 },
    body: { padding: layout.compact ? 14 : 24, gap: 16 },
    header: { gap: 4 },
    title: { color: theme.colors.foreground, fontSize: layout.compact ? 22 : 28, fontWeight: "700" as const },
    subtitle: { color: theme.colors.foregroundMuted, fontSize: 13 },
    card: { backgroundColor: theme.colors.surface2, borderColor: theme.colors.border, borderWidth: 1, borderRadius: 10, padding: 14, gap: 8 },
    cardTitle: { color: theme.colors.foreground, fontSize: 18, fontWeight: "600" as const },
    text: { color: theme.colors.foreground, fontSize: 14 },
    muted: { color: theme.colors.foregroundMuted, fontSize: 13 },
    danger: { color: theme.colors.statusDanger, fontSize: 14 },
    button: { alignSelf: "flex-start" as const, borderColor: theme.colors.border, borderWidth: 1, borderRadius: 8, paddingVertical: 7, paddingHorizontal: 11 },
    buttonText: { color: theme.colors.foreground, fontSize: 13 },
    signal: { color: theme.colors.foreground, fontSize: 13 },
    signalDanger: { color: theme.colors.statusDanger, fontSize: 13 },
    gap: { gap: 4 },
  }), [theme, layout.compact]);

  // A failed refresh must not keep presenting the previous snapshot as current.
  const data = query.error ? undefined : query.data;
  const rooms = data?.rooms ?? [];
  const visibleRooms = showHistory ? rooms : rooms.filter((room) => room.leaseState === "active" || room.leaseState === "pending");
  const active = rooms.filter((room) => room.leaseState === "active").length;
  const attention = rooms.reduce((count, room) => count + (room.leaseState === "active" ? room.signals.filter((signal) => signal.level !== "info").length : 0), 0);
  const shadow = rooms.reduce((count, room) => count + (room.leaseState === "active" ? room.signals.filter((signal) => signal.level === "info").length : 0), 0);

  const seatLine = (seat: Seat | null, fallback: string) => seat
    ? `${seat.role}: ${seat.title} · ${seat.status} · ${seat.taskState}${seat.pendingPermissions ? ` · ${seat.pendingPermissions} permission pending` : ""}`
    : fallback;
  const signalLine = (signal: Signal) => `${signal.level === "info" ? "Shadow" : signal.level === "critical" ? "Critical" : "Attention"}: ${signal.message}`;

  function roomCard(room: Room) {
    return (
      <View key={room.workspaceId} style={styles.card}>
        <Text style={styles.cardTitle}>{room.workspaceName}</Text>
        <Text style={styles.muted}>{room.workspaceId}</Text>
        <Text style={styles.text}>Lease {room.leaseState} · {room.authorityMode} · epoch {room.workEpoch} · revision {room.revision}</Text>
        <Text style={styles.text}>Decision {room.decisionState}{room.humanDecision ? ` · Human ${room.humanDecision}` : ""} · {room.reportCount} recorded reports · candidate {room.candidatePresent ? "recorded" : "not recorded"}</Text>
        <View style={styles.gap}>
          <Text style={styles.text}>{seatLine(room.lead, "Lead: not found in current Paseo list")}</Text>
          {room.supervisor ? <Text style={styles.text}>{seatLine(room.supervisor, "")}</Text> : null}
          {room.peers.map((peer) => <Text key={peer.id} style={styles.text}>{seatLine(peer, "")}</Text>)}
        </View>
        {room.openAsks.map((ask) => (
          <View key={ask.id} style={styles.gap}>
            <Text style={styles.text}>Open ask {ask.id}: {ask.question}</Text>
            <Text style={styles.muted}>For {ask.recipientAgentId} · opened {ask.createdAt}</Text>
          </View>
        ))}
        {room.signals.map((signal, index) => (
          <Text key={`${signal.code}:${signal.seatId ?? "room"}:${index}`} style={signal.level === "critical" ? styles.signalDanger : styles.signal}>
            {signalLine(signal)}
          </Text>
        ))}
      </View>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.body}>
      <View style={styles.header}>
        <Text style={styles.title}>Room Flow</Text>
        <Text style={styles.subtitle}>Read-only view of Paseo sessions and room-kit leases. Refreshes every 15 seconds.</Text>
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel="Refresh Room Flow" onPress={() => void query.refetch()} style={styles.button}>
        <Text style={styles.buttonText}>{query.isFetching ? "Refreshing…" : "Refresh"}</Text>
      </Pressable>
      {query.isLoading ? <Text style={styles.muted}>Reading Paseo and room leases…</Text> : null}
      {query.error ? <Text style={styles.danger}>Flow unavailable: {String(query.error)}</Text> : null}
      {data ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Health</Text>
          <Text style={styles.text}>{active} active rooms · {attention} attention signals · {shadow} shadow signals</Text>
          <Text style={styles.muted}>Snapshot {data.generatedAt}</Text>
          {data.leaseSource === "missing" ? <Text style={styles.muted}>No room-kit lease registry exists on this daemon host.</Text> : null}
          <Text style={styles.muted}>Signals are observations. They never accept work, change authority, or contact agents.</Text>
        </View>
      ) : null}
      {data && rooms.length === 0 ? <Text style={styles.muted}>No room-kit bindings in the lease registry.</Text> : null}
      {data && rooms.some((room) => room.leaseState !== "active" && room.leaseState !== "pending") ? (
        <Pressable accessibilityRole="button" accessibilityLabel={showHistory ? "Hide released rooms" : "Show released rooms"} onPress={() => setShowHistory(!showHistory)} style={styles.button}>
          <Text style={styles.buttonText}>{showHistory ? "Hide released rooms" : `Show ${rooms.length - visibleRooms.length} released rooms`}</Text>
        </Pressable>
      ) : null}
      {visibleRooms.map(roomCard)}
    </ScrollView>
  );
}
