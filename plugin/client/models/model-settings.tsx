import { useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { ModelOption, ModelSettingsProps, RoleRoute } from "../../shared/models/types.ts";

// Optional role boundary supplied by the host. Without it every catalog model is
// offered to every role; with it, models outside the role stay visible but disabled.
type Props = ModelSettingsProps & {
  modelsForRole?: (roleId: string, catalog: ModelOption[]) => ModelOption[];
};

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; message: string }
  | { kind: "error"; message: string };

const ALL = "all";

export const modelKeyOf = (model: ModelOption) => `${model.provider}/${model.id}`;

export function ModelSettings({ theme, layout, catalog, initialRoutes, onSave, modelsForRole }: Props) {
  const c = theme.colors;
  const compact = layout.compact;
  // initialRoutes is treated as a stable snapshot for this preview; later prop
  // changes are not merged into an in-progress draft.
  const [baseline, setBaseline] = useState<RoleRoute[]>(initialRoutes);
  const [draft, setDraft] = useState<RoleRoute[]>(initialRoutes);
  const [roleId, setRoleId] = useState(initialRoutes[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState(ALL);
  const [notices, setNotices] = useState<Record<string, string>>({});
  const [reviewOpen, setReviewOpen] = useState(false);
  const [save, setSave] = useState<SaveState>({ kind: "idle" });
  const saving = useRef(false);

  const byKey = useMemo(() => new Map(catalog.map((model) => [modelKeyOf(model), model])), [catalog]);
  const route = draft.find((item) => item.id === roleId) ?? draft[0];
  const before = (id: string) => baseline.find((item) => item.id === id);
  const changed = draft.filter((item) => {
    const prior = before(item.id);
    return !prior || prior.modelKey !== item.modelKey || prior.effort !== item.effort;
  });
  const isChanged = (item: RoleRoute) => changed.some((entry) => entry.id === item.id);
  const modelName = (key: string) => byKey.get(key)?.name ?? key;
  const summary = (item: RoleRoute) => `${modelName(item.modelKey)} · ${item.effort}`;

  // Only models the role may use are listed; the allowed set still gates
  // chooseModel so the role boundary holds even if a row slips through.
  const roleCatalog = useMemo(() => {
    if (!route) return [];
    return modelsForRole ? modelsForRole(route.id, catalog) : catalog;
  }, [route?.id, catalog, modelsForRole]);
  const allowed = useMemo(() => new Set(roleCatalog.map(modelKeyOf)), [roleCatalog]);
  const providers = useMemo(() => [...new Set(roleCatalog.map((model) => model.provider))], [roleCatalog]);
  // A provider tab chosen on another role falls back to all providers here.
  const activeProvider = providers.includes(provider) ? provider : ALL;

  const disabledReason = (model: ModelOption) => {
    if (!route) return null;
    if (!allowed.has(modelKeyOf(model))) return `Not offered for ${route.name}`;
    if (!model.available) return "Unavailable in this snapshot";
    if (model.efforts.length === 0) return "No effort levels listed";
    return null;
  };

  function selectRole(id: string) {
    setRoleId(id);
    setProvider(ALL);
  }

  const needle = query.trim().toLowerCase();
  const visible = roleCatalog
    .filter((model) => activeProvider === ALL || model.provider === activeProvider)
    .filter((model) => !needle || [model.name, model.id, model.provider, model.description].some((field) => field.toLowerCase().includes(needle)))
    .map((model) => ({ model, reason: disabledReason(model) }))
    .sort((a, b) => Number(a.reason !== null) - Number(b.reason !== null));

  const current = route ? byKey.get(route.modelKey) : undefined;
  const currentEfforts = current && current.available ? current.efforts : [];
  const effortSupported = current ? current.efforts.includes(route?.effort ?? "") : false;

  function touch() {
    if (save.kind === "saved" || save.kind === "error") setSave({ kind: "idle" });
  }

  function update(next: Partial<RoleRoute>) {
    if (!route) return;
    setDraft((items) => items.map((item) => (item.id === route.id ? { ...item, ...next } : item)));
    touch();
  }

  function chooseModel(model: ModelOption) {
    if (!route || disabledReason(model) || modelKeyOf(model) === route.modelKey) return;
    const prior = byKey.get(route.modelKey);
    // Effort labels are provider-defined; "high" on one provider is not the same
    // setting on another, so the effort only carries over within a provider.
    const sameProvider = prior?.provider === model.provider;
    const keep = sameProvider && model.efforts.includes(route.effort);
    const effort = keep ? route.effort : model.efforts[0];
    update({ modelKey: modelKeyOf(model), effort });
    setNotices((items) => {
      const rest = { ...items };
      delete rest[route.id];
      if (keep || effort === route.effort) return rest;
      const why = sameProvider
        ? `${model.name} doesn't offer ${route.effort}.`
        : "Effort levels aren't comparable across providers.";
      return { ...rest, [route.id]: `Effort set to ${effort}. ${why}` };
    });
  }

  function chooseEffort(effort: string) {
    if (!route) return;
    update({ effort });
    setNotices((items) => {
      const rest = { ...items };
      delete rest[route.id];
      return rest;
    });
  }

  function discard() {
    if (saving.current) return;
    setDraft(baseline);
    setNotices({});
    setReviewOpen(false);
    setSave({ kind: "idle" });
  }

  async function commit() {
    if (saving.current || changed.length === 0) return;
    saving.current = true;
    const submitted = draft;
    setSave({ kind: "saving" });
    try {
      if (onSave) await onSave(submitted);
      // Only the submitted snapshot becomes the baseline; edits made while the
      // save was pending remain as unsaved changes.
      setBaseline(submitted);
      setNotices({});
      setReviewOpen(false);
      setSave({
        kind: "saved",
        message: onSave ? "Saved · applies to new agents only" : "Preview saved · settings are not applied to agents",
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setSave({ kind: "error", message: `Couldn't save: ${detail}. Your edits are kept; try again.` });
    } finally {
      saving.current = false;
    }
  }

  const s = useMemo(() => {
    const target = compact ? 44 : 36;
    return {
      screen: { flex: 1, backgroundColor: c.surface0 },
      header: { paddingHorizontal: compact ? 16 : 24, paddingTop: compact ? 16 : 22, paddingBottom: 14, gap: 4, borderBottomWidth: 1, borderBottomColor: c.border },
      title: { color: c.foreground, fontSize: compact ? 22 : 24, fontWeight: "700" as const, letterSpacing: -0.3 },
      subtitle: { color: c.foregroundMuted, fontSize: 13, lineHeight: 18 },
      body: { flex: 1, flexDirection: compact ? ("column" as const) : ("row" as const) },
      nav: { width: 240, flexGrow: 0, flexShrink: 0, flexBasis: 240, borderRightWidth: 1, borderRightColor: c.border, backgroundColor: c.surface1 },
      navBody: { paddingVertical: 12, paddingHorizontal: 8, gap: 2 },
      navLabel: { color: c.foregroundMuted, fontSize: 12, fontWeight: "600" as const, paddingHorizontal: 10, paddingBottom: 6 },
      navItem: { minHeight: 52, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 8, gap: 2, justifyContent: "center" as const },
      navItemActive: { backgroundColor: c.surface2 },
      navRow: { flexDirection: "row" as const, alignItems: "center" as const, gap: 8 },
      navName: { color: c.foreground, fontSize: 14, fontWeight: "600" as const, flexShrink: 1 },
      navMeta: { color: c.foregroundMuted, fontSize: 12 },
      dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: c.accent },
      chips: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
      chip: { minHeight: 52, minWidth: 132, maxWidth: 200, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface1, gap: 2, justifyContent: "center" as const },
      chipActive: { borderColor: c.accent, backgroundColor: c.surface2 },
      detail: { flexGrow: 1, flexShrink: 1, flexBasis: 0, minWidth: 0 },
      detailBody: { padding: compact ? 16 : 24, gap: 24, maxWidth: 760 },
      section: { gap: 10 },
      roleName: { color: c.foreground, fontSize: 18, fontWeight: "600" as const, letterSpacing: -0.2 },
      text: { color: c.foreground, fontSize: 14, lineHeight: 20 },
      muted: { color: c.foregroundMuted, fontSize: 13, lineHeight: 18 },
      small: { color: c.foregroundMuted, fontSize: 12, lineHeight: 16 },
      label: { color: c.foreground, fontSize: 13, fontWeight: "600" as const },
      warning: { color: c.statusWarning, fontSize: 13, lineHeight: 18 },
      danger: { color: c.statusDanger, fontSize: 13, lineHeight: 18 },
      success: { color: c.statusSuccess, fontSize: 13, lineHeight: 18 },
      segments: { flexDirection: "row" as const, alignSelf: compact ? ("stretch" as const) : ("flex-start" as const), borderWidth: 1, borderColor: c.border, borderRadius: 8, padding: 2, backgroundColor: c.surface1 },
      segment: { minHeight: target, minWidth: 72, flexGrow: compact ? 1 : 0, paddingHorizontal: 14, borderRadius: 6, alignItems: "center" as const, justifyContent: "center" as const },
      segmentActive: { backgroundColor: c.accent },
      segmentText: { color: c.foreground, fontSize: 13, fontWeight: "500" as const },
      segmentTextActive: { color: c.accentForeground, fontSize: 13, fontWeight: "600" as const },
      search: { minHeight: target + 4, borderWidth: 1, borderColor: c.border, borderRadius: 8, paddingHorizontal: 12, color: c.foreground, backgroundColor: c.surface1, fontSize: 14 },
      tabs: { gap: 6 },
      tab: { minHeight: target, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: c.border, alignItems: "center" as const, justifyContent: "center" as const },
      tabActive: { backgroundColor: c.surface2, borderColor: c.foregroundMuted },
      tabText: { color: c.foregroundMuted, fontSize: 13 },
      tabTextActive: { color: c.foreground, fontSize: 13, fontWeight: "600" as const },
      list: { borderWidth: 1, borderColor: c.border, borderRadius: 10, overflow: "hidden" as const },
      row: { minHeight: 60, flexDirection: "row" as const, gap: 12, paddingVertical: 12, paddingHorizontal: 14, alignItems: "flex-start" as const },
      rowDivider: { borderTopWidth: 1, borderTopColor: c.border },
      rowActive: { backgroundColor: c.surface2 },
      rowPressed: { backgroundColor: c.surface1 },
      radio: { width: 16, height: 16, marginTop: 2, borderRadius: 8, borderWidth: 1.5, borderColor: c.foregroundMuted, alignItems: "center" as const, justifyContent: "center" as const },
      radioOn: { borderColor: c.accent },
      radioOff: { borderColor: c.border },
      radioDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: c.accent },
      rowMain: { flex: 1, gap: 3 },
      rowTop: { flexDirection: "row" as const, flexWrap: "wrap" as const, alignItems: "baseline" as const, columnGap: 8 },
      rowName: { color: c.foreground, fontSize: 14, fontWeight: "600" as const },
      rowNameOff: { color: c.foregroundMuted, fontSize: 14, fontWeight: "600" as const },
      footer: { borderTopWidth: 1, borderTopColor: c.border, backgroundColor: c.surface1, paddingHorizontal: compact ? 16 : 24, paddingVertical: 12, gap: 10 },
      footerRow: { flexDirection: compact ? ("column" as const) : ("row" as const), alignItems: compact ? ("stretch" as const) : ("center" as const), gap: compact ? 10 : 16 },
      footerStatus: { flexGrow: compact ? 0 : 1, flexShrink: 0, flexBasis: "auto" as const, gap: 2 },
      actions: { flexDirection: "row" as const, gap: 8 },
      button: { minHeight: target, paddingHorizontal: 14, borderRadius: 8, borderWidth: 1, borderColor: c.border, alignItems: "center" as const, justifyContent: "center" as const, flexGrow: compact ? 1 : 0 },
      buttonPrimary: { borderColor: c.accent, backgroundColor: c.accent },
      buttonOff: { borderColor: c.border, backgroundColor: c.surface2 },
      buttonText: { color: c.foreground, fontSize: 13, fontWeight: "500" as const },
      buttonPrimaryText: { color: c.accentForeground, fontSize: 13, fontWeight: "600" as const },
      buttonOffText: { color: c.foregroundMuted, fontSize: 13, fontWeight: "500" as const },
      link: { minHeight: compact ? 44 : 28, alignSelf: "flex-start" as const, justifyContent: "center" as const },
      linkText: { color: c.accent, fontSize: 13, fontWeight: "500" as const },
      review: { maxHeight: compact ? 220 : 200, borderWidth: 1, borderColor: c.border, borderRadius: 8, backgroundColor: c.surface0 },
      reviewBody: { padding: 12, gap: 12 },
      reviewItem: { gap: 4 },
      compare: { flexDirection: "row" as const, gap: 8 },
      compareKey: { color: c.foregroundMuted, fontSize: 12, width: 48, lineHeight: 18 },
      compareOld: { color: c.foregroundMuted, fontSize: 13, lineHeight: 18, flex: 1 },
      compareNew: { color: c.foreground, fontSize: 13, lineHeight: 18, fontWeight: "500" as const, flex: 1 },
      count: { color: c.foreground, fontSize: 13, fontWeight: "600" as const, fontVariant: ["tabular-nums" as const] },
    };
  }, [c, compact]);

  if (!route) {
    return (
      <View style={s.screen}>
        <View style={s.header}>
          <Text accessibilityRole="header" style={s.title}>Model & effort</Text>
          <Text style={s.subtitle}>No roles in this snapshot.</Text>
        </View>
      </View>
    );
  }

  const roleNav = compact ? (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips} accessibilityRole="tablist" style={{ flexGrow: 0, borderBottomWidth: 1, borderBottomColor: c.border }}>
      {draft.map((item) => {
        const active = item.id === route.id;
        return (
          <Pressable key={item.id} accessibilityRole="tab" aria-selected={active} accessibilityLabel={`${item.name}: ${summary(item)}${isChanged(item) ? ", changed" : ""}`} onPress={() => selectRole(item.id)} style={[s.chip, active && s.chipActive]}>
            <View style={s.navRow}>
              <Text numberOfLines={1} style={s.navName}>{item.name}</Text>
              {isChanged(item) ? <View style={s.dot} /> : null}
            </View>
            <Text numberOfLines={1} style={s.navMeta}>{summary(item)}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  ) : (
    <ScrollView style={s.nav} contentContainerStyle={s.navBody} accessibilityRole="tablist">
      <Text style={s.navLabel}>Roles</Text>
      {draft.map((item) => {
        const active = item.id === route.id;
        return (
          <Pressable key={item.id} accessibilityRole="tab" aria-selected={active} accessibilityLabel={`${item.name}: ${summary(item)}${isChanged(item) ? ", changed" : ""}`} onPress={() => selectRole(item.id)} style={({ pressed }) => [s.navItem, (active || pressed) && s.navItemActive]}>
            <View style={s.navRow}>
              <Text numberOfLines={1} style={s.navName}>{item.name}</Text>
              {isChanged(item) ? <View style={s.dot} /> : null}
            </View>
            <Text numberOfLines={1} style={s.navMeta}>{summary(item)}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );

  const prior = before(route.id);
  const notice = notices[route.id];

  const detail = (
    <View style={s.detailBody}>
      <View style={s.section}>
        <View style={{ gap: 4 }}>
          <Text accessibilityRole="header" style={s.roleName}>{route.name}</Text>
          <Text style={s.muted}>{route.description}</Text>
        </View>
        <View style={{ gap: 2 }}>
          <Text style={s.text}>{current ? current.name : route.modelKey}</Text>
          <Text style={s.small}>{current ? `${current.provider} · ${current.id}` : "Not in this catalog snapshot"}</Text>
        </View>
        {current && !current.available ? <Text style={s.warning}>This model is unavailable in this snapshot. Choose another model below.</Text> : null}
        {!current ? <Text style={s.warning}>The current model isn't in this snapshot. Choose a model below.</Text> : null}
      </View>

      <View style={s.section}>
        <Text style={s.label}>Effort</Text>
        {currentEfforts.length > 0 ? (
          <View style={s.segments} accessibilityRole="radiogroup" accessibilityLabel={`Effort for ${route.name}`}>
            {currentEfforts.map((effort) => {
              const active = effort === route.effort;
              return (
                <Pressable key={effort} accessibilityRole="radio" aria-checked={active} accessibilityLabel={`${effort} effort`} onPress={() => chooseEffort(effort)} style={[s.segment, active && s.segmentActive]}>
                  <Text style={active ? s.segmentTextActive : s.segmentText}>{effort}</Text>
                </Pressable>
              );
            })}
          </View>
        ) : (
          <Text style={s.muted}>Current: {route.effort}. Choose an available model to set effort.</Text>
        )}
        {currentEfforts.length > 0 && !effortSupported ? <Text style={s.warning}>{route.effort} isn't listed for {current?.name}. Pick a supported effort.</Text> : null}
        {notice ? <Text accessibilityLiveRegion="polite" style={s.warning}>{notice}</Text> : null}
        {currentEfforts.length === 1 ? <Text style={s.small}>{current?.name} lists one effort level.</Text> : null}
      </View>

      <View style={s.section}>
        <Text style={s.label}>Model</Text>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search models or providers"
          placeholderTextColor={c.foregroundMuted}
          selectionColor={c.accent}
          cursorColor={c.accent}
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel="Search models"
          style={s.search}
        />
        {providers.length > 1 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={s.tabs} accessibilityRole="tablist">
            {[ALL, ...providers].map((item) => {
              const active = item === activeProvider;
              const label = item === ALL ? "All providers" : item;
              return (
                <Pressable key={item} accessibilityRole="tab" aria-selected={active} accessibilityLabel={label} onPress={() => setProvider(item)} style={[s.tab, active && s.tabActive]}>
                  <Text style={active ? s.tabTextActive : s.tabText}>{label}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
        ) : null}
        {roleCatalog.length === 0 ? (
          <Text style={s.muted}>No models are offered for {route.name} in this snapshot.</Text>
        ) : visible.length === 0 ? (
          <View style={{ gap: 4 }}>
            <Text style={s.muted}>No matches{needle ? ` for "${query.trim()}"` : ""}{activeProvider !== ALL ? ` in ${activeProvider}` : ""}.</Text>
            <Pressable accessibilityRole="button" onPress={() => { setQuery(""); setProvider(ALL); }} style={s.link}>
              <Text style={s.linkText}>Clear filters</Text>
            </Pressable>
          </View>
        ) : (
          <View style={s.list} accessibilityRole="radiogroup" accessibilityLabel={`Model for ${route.name}`}>
            {visible.map(({ model, reason }, index) => {
              const key = modelKeyOf(model);
              const active = key === route.modelKey;
              const off = reason !== null && !active;
              return (
                <Pressable
                  key={key}
                  accessibilityRole="radio"
                  aria-checked={active}
                  aria-disabled={off}
                  disabled={off}
                  accessibilityLabel={`${model.name}, ${model.provider}${reason ? `, ${reason}` : ""}`}
                  onPress={() => chooseModel(model)}
                  style={({ pressed }) => [s.row, index > 0 && s.rowDivider, active ? s.rowActive : pressed && !off ? s.rowPressed : null]}
                >
                  <View style={[s.radio, active ? s.radioOn : off ? s.radioOff : null]}>
                    {active ? <View style={s.radioDot} /> : null}
                  </View>
                  <View style={s.rowMain}>
                    <View style={s.rowTop}>
                      <Text style={off ? s.rowNameOff : s.rowName}>{model.name}</Text>
                      <Text style={s.small}>{model.provider}</Text>
                    </View>
                    <Text style={s.muted}>{model.description}</Text>
                    {reason ? (
                      <Text style={s.small}>{reason}</Text>
                    ) : (
                      <Text style={s.small}>Effort: {model.efforts.join(", ")}</Text>
                    )}
                  </View>
                </Pressable>
              );
            })}
          </View>
        )}
        <Text style={s.small}>Catalog is a demo snapshot. It does not reflect live availability.</Text>
      </View>
      {prior && isChanged(route) ? <Text style={s.small}>Saved value: {summary(prior)}</Text> : null}
    </View>
  );

  const pending = save.kind === "saving";
  const canSave = changed.length > 0 && !pending;
  const canDiscard = changed.length > 0 && !pending;

  return (
    <View style={s.screen}>
      <View style={s.header}>
        <Text accessibilityRole="header" style={s.title}>Model & effort</Text>
        <Text style={s.subtitle}>Interactive preview · changes stay in this screen.</Text>
        <Text style={s.subtitle}>Defaults for new agents in each role. Running agents keep their current model.</Text>
      </View>
      {compact ? (
        <ScrollView style={s.detail} keyboardShouldPersistTaps="handled">
          {roleNav}
          {detail}
        </ScrollView>
      ) : (
        <View style={s.body}>
          {roleNav}
          <ScrollView style={s.detail} keyboardShouldPersistTaps="handled">{detail}</ScrollView>
        </View>
      )}
      <View style={s.footer}>
        {reviewOpen && changed.length > 0 ? (
          <ScrollView style={s.review} contentContainerStyle={s.reviewBody} accessibilityLabel="Change summary">
            {changed.map((item) => {
              const was = before(item.id);
              return (
                <View key={item.id} style={s.reviewItem}>
                  <Text style={s.label}>{item.name}</Text>
                  <View style={s.compare}>
                    <Text style={s.compareKey}>Before</Text>
                    <Text style={s.compareOld}>{was ? summary(was) : "Not set"}</Text>
                  </View>
                  <View style={s.compare}>
                    <Text style={s.compareKey}>After</Text>
                    <Text style={s.compareNew}>{summary(item)}</Text>
                  </View>
                </View>
              );
            })}
          </ScrollView>
        ) : null}
        <View style={s.footerRow}>
          <View style={s.footerStatus} accessibilityLiveRegion="polite">
            {changed.length > 0 ? (
              <View style={[s.navRow, { flexWrap: "wrap" }]}>
                <Text style={s.count}>{changed.length} unsaved {changed.length === 1 ? "change" : "changes"}</Text>
                <Pressable accessibilityRole="button" aria-expanded={reviewOpen} accessibilityLabel={reviewOpen ? "Hide change summary" : "Review changes"} onPress={() => setReviewOpen(!reviewOpen)} style={s.link}>
                  <Text style={s.linkText}>{reviewOpen ? "Hide changes" : "Review changes"}</Text>
                </Pressable>
              </View>
            ) : save.kind !== "saved" ? (
              <Text style={s.muted}>No unsaved changes</Text>
            ) : null}
            {pending ? <Text style={s.muted}>Saving…</Text> : null}
            {save.kind === "saved" ? <Text style={s.success}>{save.message}</Text> : null}
            {save.kind === "error" ? <Text style={s.danger}>{save.message}</Text> : null}
          </View>
          <View style={s.actions}>
            <Pressable accessibilityRole="button" aria-disabled={!canDiscard} disabled={!canDiscard} onPress={discard} style={[s.button, !canDiscard && s.buttonOff]}>
              <Text style={canDiscard ? s.buttonText : s.buttonOffText}>Discard changes</Text>
            </Pressable>
            <Pressable accessibilityRole="button" aria-disabled={!canSave} aria-busy={pending} disabled={!canSave} onPress={() => void commit()} style={[s.button, canSave ? s.buttonPrimary : s.buttonOff]}>
              <Text style={canSave ? s.buttonPrimaryText : s.buttonOffText}>{pending ? "Saving…" : "Save preview"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}
