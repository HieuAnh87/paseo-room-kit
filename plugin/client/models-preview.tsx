import type { PluginSurfaceProps } from '@getpaseo/plugin/client';
import { ModelSettings } from './models/model-settings.tsx';
import { catalog, catalogForRole, initialRoutes } from '../shared/models/fixture.ts';

export function ModelsPreviewSurface({theme,layout}:PluginSurfaceProps){
  return <ModelSettings theme={theme} layout={layout} catalog={catalog} modelsForRole={catalogForRole} initialRoutes={initialRoutes}/>;
}
