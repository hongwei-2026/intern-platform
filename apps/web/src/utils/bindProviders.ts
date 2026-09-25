/** Platform binding providers — consumer-facing account link meta. */

export type BindProvider = 'github' | 'gitee' | 'gitcode' | 'gitlink' | 'gitea'

export type BindField = 'github_id' | 'gitee_id' | 'gitcode_id' | 'gitlink_id' | 'gitea_id'

export interface BindProviderMeta {
  key: BindProvider
  field: BindField
  name: string
  desc: string
  color: string
  /** Brand mark letter when no SVG */
  mark: string
  /** Prefer showing in primary list */
  recommended?: boolean
}

export const BIND_PROVIDERS: BindProviderMeta[] = [
  {
    key: 'github',
    field: 'github_id',
    name: 'GitHub',
    desc: '国际主流开源托管',
    color: '#24292f',
    mark: 'GH',
    recommended: true,
  },
  {
    key: 'gitee',
    field: 'gitee_id',
    name: 'Gitee',
    desc: '码云代码托管',
    color: '#c71d23',
    mark: '码',
    recommended: true,
  },
  {
    key: 'gitcode',
    field: 'gitcode_id',
    name: 'GitCode',
    desc: '国内开源托管',
    color: '#c7000b',
    mark: 'GC',
    recommended: true,
  },
  {
    key: 'gitlink',
    field: 'gitlink_id',
    name: 'GitLink',
    desc: '开源托管社区',
    color: '#0b5fff',
    mark: 'GL',
  },
  {
    key: 'gitea',
    field: 'gitea_id',
    name: '俱乐部 Gitea',
    desc: '俱乐部代码托管',
    color: '#609926',
    mark: 'Gt',
  },
]

export function getProvider(key: string): BindProviderMeta | undefined {
  return BIND_PROVIDERS.find((p) => p.key === key)
}
