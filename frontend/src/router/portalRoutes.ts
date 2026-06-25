import type { User } from '@/types';

type AdminRole = 'admin' | 'super_admin';
type PortalRole = User['role'];
type PortalTarget =
  | 'dashboard'
  | 'leads'
  | 'manualCallbacks'
  | 'knowledgeBase'
  | 'systemPrompt'
  | 'systemSettings'
  | 'userManagement';

interface PortalPathOptions {
  id?: string;
}

const SUPER_ADMIN_BASE = '/admin-system';
const SCHOOL_ADMIN_BASE = '/expo-system';
const TEACHER_BASE = '/expo-system/user';
const PARENT_CONVERSATION_BASE = '/expoagent/conversations';
const EXACT_MATCH_MENU_PATHS = new Set([SUPER_ADMIN_BASE, SCHOOL_ADMIN_BASE, TEACHER_BASE]);
const SCHOOL_ADMIN_LOCKED_TARGETS: PortalTarget[] = [
  'manualCallbacks',
  'systemPrompt',
  'userManagement',
  'systemSettings',
];

export function isAdminPortalRole(role: PortalRole | null | undefined): role is AdminRole {
  return role === 'admin' || role === 'super_admin';
}

export function isTeacherPortalRole(role: PortalRole | null | undefined): role is 'sales' {
  return role === 'sales';
}

export function getPortalHomePath(role: PortalRole | null | undefined): string {
  if (role === 'super_admin') {
    return SUPER_ADMIN_BASE;
  }
  if (role === 'admin') {
    return SCHOOL_ADMIN_BASE;
  }
  if (isTeacherPortalRole(role)) {
    return TEACHER_BASE;
  }
  return '/auth/login';
}

export function getPortalPath(role: PortalRole | null | undefined, target: PortalTarget): string {
  const base = getPortalHomePath(role);

  switch (target) {
    case 'dashboard':
      return base;
    case 'userManagement':
      return `${base}/users`;
    case 'leads':
      return `${base}/leads`;
    case 'manualCallbacks':
      return `${base}/manual-callbacks`;
    case 'knowledgeBase':
      return `${base}/knowledge-base`;
    case 'systemPrompt':
      return `${base}/system-prompt`;
    case 'systemSettings':
      return `${base}/system-settings`;
    default:
      return base;
  }
}

export function getPortalConversationPath(
  role: PortalRole | null | undefined,
  conversationId: string,
): string {
  return `${getPortalHomePath(role)}/conversation/${conversationId}`;
}

export function getParentConversationPath(conversationId: string): string {
  return `${PARENT_CONVERSATION_BASE}/${conversationId}`;
}

export function getPortalLeadDetailPath(
  role: PortalRole | null | undefined,
  leadId: string,
): string {
  return `${getPortalPath(role, 'leads')}/${leadId}`;
}

export function isPortalMenuPathActive(currentPath: string, itemPath: string): boolean {
  if (EXACT_MATCH_MENU_PATHS.has(itemPath)) {
    return currentPath === itemPath;
  }
  return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
}

export function isSchoolAdminFeatureLocked(
  role: PortalRole | null | undefined,
  currentPath: string,
): boolean {
  if (role !== 'admin') {
    return false;
  }

  return SCHOOL_ADMIN_LOCKED_TARGETS.some((target) =>
    isPortalMenuPathActive(currentPath, getPortalPath(role, target)),
  );
}

export function getPortalRouteLocation(
  role: PortalRole | null | undefined,
  target: PortalTarget,
  options: PortalPathOptions = {},
): string {
  if (target === 'leads' && options.id) {
    return getPortalLeadDetailPath(role, options.id);
  }
  if (target === 'dashboard' && options.id) {
    return getPortalConversationPath(role, options.id);
  }
  return getPortalPath(role, target);
}
