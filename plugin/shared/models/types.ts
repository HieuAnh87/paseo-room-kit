import type { PluginTheme } from '@getpaseo/plugin';

export type ModelOption = {
  id: string;
  provider: string;
  name: string;
  description: string;
  efforts: string[];
  available: boolean;
};
export type RoleRoute = {
  id: string;
  name: string;
  description: string;
  modelKey: string;
  effort: string;
};
export type ModelSettingsProps = {
  theme: PluginTheme;
  layout: { compact: boolean; platform: 'web' | 'ios' | 'android' };
  catalog: ModelOption[];
  initialRoutes: RoleRoute[];
  onSave?: (routes: RoleRoute[]) => Promise<void>;
};
