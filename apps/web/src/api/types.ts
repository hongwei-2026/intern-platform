export interface RoleOut {
  code: string
  community_id?: number | null
}

export interface UserOut {
  id: number
  email: string
  display_name: string
  school?: string | null
  github_id?: string | null
  gitea_id?: string | null
  gitcode_id?: string | null
  gitee_id?: string | null
  gitlink_id?: string | null
  oauth_avatars?: Record<string, string>
  member_no?: string | null
  bio?: string | null
  phone?: string | null
  major?: string | null
  grade?: string | null
  degree?: string | null
  homepage_url?: string | null
  contact_email?: string | null
  city?: string | null
  auth_provider: string
  roles: RoleOut[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserOut
}

export interface PortalLinksOut {
  home_url?: string | null
  docs_url?: string | null
  join_guide_url?: string | null
  gitea_url?: string | null
  mirror_url?: string | null
  raw?: Record<string, string | null>
}

export interface IntroBlock {
  id?: string
  type: 'paragraph' | 'heading' | 'image' | 'table' | 'video'
  text?: string
  url?: string
  caption?: string
  headers?: string[]
  rows?: string[][]
}

export interface CommunityIntroBody {
  blocks: IntroBlock[]
}

export interface CommunityOut {
  id: number
  name: string
  slug: string
  description?: string | null
  logo_url?: string | null
  homepage_url?: string | null
  mirror_doc_url?: string | null
  gitea_org_url?: string | null
  status: string
  invite_code?: string | null
  tags?: string[]
  intro_body?: CommunityIntroBody | null
}

export interface CommunityMemberOut {
  user_id: number
  display_name: string
  email: string
  role: string
  community_id?: number | null
  community_name?: string | null
  role_label?: string | null
}

export interface ExtensionOut {
  community_id: number
  profile_blocks?: string | null
  application_schema?: string | null
  final_schema?: string | null
  enabled_modules?: string | null
}

export interface ProjectAssigneeOut {
  application_id: number
  student_id: number
  student_name?: string | null
  status: string
  kind?: 'assigned' | 'reserved' | 'reviewing' | string
}

export interface ProjectOut {
  id: number
  community_id: number
  mentor_id: number
  title: string
  summary?: string | null
  description?: string | null
  tech_stack?: string | null
  difficulty?: string | null
  quota: number
  repo_url?: string | null
  apply_deadline?: string | null
  status: string
  assignees?: ProjectAssigneeOut[]
  applicants_reviewing?: ProjectAssigneeOut[]
  seats_taken?: number
  seats_available?: number | null
  reviewing_count?: number
  mentor_name?: string | null
  mentor_email?: string | null
}

/** 昇腾式任务动态行（项目维度，昵称脱敏） */
export interface TaskDynamicsRow {
  application_id: number
  nickname: string
  avatar_letter: string
  registered_at?: string | null
  last_progress_at?: string | null
  progress_count: number
  last_acceptance_at?: string | null
  acceptance_passed_at?: string | null
  progress_label: string
  progress_tone: string
}

export interface ApplicationOut {
  id: number
  project_id: number
  student_id: number
  student_name?: string | null
  student_email?: string | null
  statement?: string | null
  attachment_url?: string | null
  extra_fields?: string | null
  resume_pdf?: string | null
  design_pdf?: string | null
  status: string
  current_node: string
  version: number
  project_title?: string | null
  latest_update_at?: string | null
  update_badge?: 'progress' | 'acceptance' | null
  review_records?: ReviewRecordOut[]
  created_at?: string | null
  updated_at?: string | null
}

export interface ReviewRecordOut {
  id?: number
  seq_no?: number
  from_status: string
  to_status: string
  action: string
  decision_code?: string | null
  actor_id?: number
  actor_role?: string
  comment?: string | null
  created_at?: string | null
}

export interface ReviewResponse {
  application_id: number
  from_status: string
  to_status: string
  action: string
  idempotent_replay: boolean
  version: number
  mail_sent?: boolean | null
  mail_hint?: string | null
}

export interface AnnouncementOut {
  id: number
  type: string
  title: string
  body?: string | null
  community_id?: number | null
  project_id?: number | null
  application_id?: number | null
  published_by: number
  published_at?: string | null
  is_public: number
}

export interface MessageOut {
  id: number
  application_id: number
  sender_id: number
  body: string
  kind?: 'note' | 'progress' | 'midterm' | 'feedback' | 'acceptance' | string
  design_doc_url?: string | null
  code_url?: string | null
  attachment_url?: string | null
  attachment_name?: string | null
  community_name?: string | null
  reward_status?: string | null
  created_at?: string | null
}

export interface FinalOut {
  id: number
  application_id: number
  pr_mr_url: string
  report_url?: string | null
  report_text?: string | null
  extra_fields?: string | null
  status: string
}

export interface NotificationOut {
  id: number
  title: string
  body?: string | null
  kind: string
  project_id?: number | null
  application_id?: number | null
  is_read: number
  created_at?: string | null
}

export interface NotificationListOut {
  items: NotificationOut[]
  unread_count: number
}
