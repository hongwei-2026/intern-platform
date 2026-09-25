/** 计算机方向两级分类：先大方向，再其下子方向。 */

export type CsChild = { id: string; label: string }
export type CsDirection = { id: string; label: string; children: CsChild[] }

export const CS_DIRECTIONS: CsDirection[] = [
  {
    id: 'systems',
    label: '计算机系统',
    children: [
      { id: 'os', label: '操作系统' },
      { id: 'arch', label: '体系结构' },
      { id: 'embedded', label: '嵌入式' },
      { id: 'compiler', label: '编译原理' },
      { id: 'hpc', label: '高性能计算' },
    ],
  },
  {
    id: 'ai',
    label: '人工智能',
    children: [
      { id: 'ml', label: '机器学习' },
      { id: 'dl', label: '深度学习' },
      { id: 'cvnlp', label: '视觉与语言' },
    ],
  },
  {
    id: 'data',
    label: '数据与存储',
    children: [
      { id: 'db', label: '数据库' },
      { id: 'bigdata', label: '大数据' },
      { id: 'storage', label: '存储系统' },
    ],
  },
  {
    id: 'se',
    label: '软件工程',
    children: [
      { id: 'tools', label: '开发工具' },
      { id: 'docs', label: '文档与协作' },
      { id: 'test', label: '测试与质量' },
    ],
  },
  {
    id: 'netsec',
    label: '网络与安全',
    children: [
      { id: 'network', label: '计算机网络' },
      { id: 'security', label: '系统安全' },
    ],
  },
  {
    id: 'infra',
    label: '基础设施',
    children: [
      { id: 'ops', label: '运维与镜像' },
      { id: 'cloud', label: '云计算' },
      { id: 'virt', label: '虚拟化' },
    ],
  },
]

const SLUG_MAP: Record<string, [string, string]> = {
  kernel: ['systems', 'os'],
  openeuler: ['systems', 'os'],
  rtthread: ['systems', 'embedded'],
  'ai-lab': ['ai', 'dl'],
  mindspore: ['ai', 'dl'],
  opengauss: ['data', 'db'],
  docs: ['se', 'docs'],
  devtools: ['se', 'tools'],
  mirror: ['infra', 'ops'],
}

export type PlacedDirection = { parentId: string; parent: string; childId: string; child: string }

export function placeDirection(slug?: string | null, title?: string | null): PlacedDirection {
  const key = (slug || '').toLowerCase()
  let pair = SLUG_MAP[key]
  const t = title || ''
  if (/spmv|稀疏矩阵/i.test(t)) pair = ['systems', 'hpc']
  if (!pair) {
    if (/spmv|稀疏|矩阵|hpc/i.test(t)) pair = ['systems', 'hpc']
    else if (/嵌入|rt-?thread/i.test(t)) pair = ['systems', 'embedded']
    else if (/数据库|gauss/i.test(t)) pair = ['data', 'db']
    else if (/镜像|运维/i.test(t)) pair = ['infra', 'ops']
    else if (/深度学习|推理|mindspore|人工智能/i.test(t)) pair = ['ai', 'dl']
    else if (/文档|指南/i.test(t)) pair = ['se', 'docs']
    else pair = ['se', 'tools']
  }
  const parent = CS_DIRECTIONS.find((d) => d.id === pair[0])
  const child = parent?.children.find((c) => c.id === pair[1])
  return {
    parentId: pair[0],
    parent: parent?.label || '软件工程',
    childId: pair[1],
    child: child?.label || '开发工具',
  }
}

export function childrenOf(parentId: string): CsChild[] {
  return CS_DIRECTIONS.find((d) => d.id === parentId)?.children || []
}
