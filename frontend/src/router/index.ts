import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import TeacherLayout from '@/components/TeacherLayout.vue';
import ParentLayout from '@/components/ParentLayout.vue';
import i18n from '@/i18n';
import { getAppStorageItem } from '@/utils/browserStorage';
import { getPortalHomePath } from './portalRoutes';
import { useFeatureGateStore } from '@/stores/featureGate';

const routes = [
  {
    path: '/',
    name: 'Index',
    component: () => import('@/views/IndexView.vue'),
  },
  {
    path: '/start-chat',
    name: 'StartChat',
    component: () => import('@/views/parent/StartChatView.vue'),
  },
  {
    path: '/auth/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
  },
  // 超级管理员后台
  {
    path: '/admin-system',
    component: TeacherLayout,
    meta: { requiresAuth: true, roles: ['super_admin'] },
    children: [
      {
        path: '',
        name: 'SuperAdminPortalHome',
        component: () => import('@/views/teacher/DashboardView.vue'),
      },
      {
        path: 'leads',
        name: 'SuperAdminLeadList',
        component: () => import('@/views/teacher/LeadsView.vue'),
      },
      {
        path: 'manual-callbacks',
        name: 'SuperAdminManualCallbacks',
        component: () => import('@/views/teacher/ManualCallbacksView.vue'),
      },
      {
        path: 'knowledge-base',
        name: 'SuperAdminKnowledgeBase',
        component: () => import('@/views/teacher/KnowledgeBaseView.vue'),
        meta: { roles: ['super_admin'] },
      },
      {
        path: 'system-prompt',
        name: 'SuperAdminSystemPrompt',
        component: () => import('@/views/teacher/SystemPromptView.vue'),
        meta: { roles: ['super_admin'] },
      },
      {
        path: 'users',
        name: 'SuperAdminUserManagement',
        component: () => import('@/views/teacher/UserManagementView.vue'),
        meta: { roles: ['super_admin'] },
      },
      {
        path: 'system-settings',
        name: 'SuperAdminSystemSettings',
        component: () => import('@/views/teacher/SystemSettingsView.vue'),
      },
      {
        path: 'conversation/:id',
        name: 'SuperAdminConversationDetail',
        component: () => import('@/views/teacher/ConversationDetailView.vue'),
      },
      {
        path: 'leads/:id',
        name: 'SuperAdminLeadDetail',
        component: () => import('@/views/teacher/LeadDetailView.vue'),
      },
    ],
  },
  // 普通管理员后台
  {
    path: '/expo-system',
    component: TeacherLayout,
    meta: { requiresAuth: true, roles: ['admin'] },
    children: [
      {
        path: '',
        name: 'SchoolAdminPortalHome',
        component: () => import('@/views/teacher/DashboardView.vue'),
      },
      {
        path: 'leads',
        name: 'SchoolAdminLeadList',
        component: () => import('@/views/teacher/LeadsView.vue'),
      },
      {
        path: 'manual-callbacks',
        name: 'SchoolAdminManualCallbacks',
        component: () => import('@/views/teacher/ManualCallbacksView.vue'),
      },
      {
        path: 'knowledge-base',
        name: 'SchoolAdminKnowledgeBase',
        component: () => import('@/views/teacher/KnowledgeBaseView.vue'),
      },
      {
        path: 'system-prompt',
        name: 'SchoolAdminSystemPrompt',
        component: () => import('@/views/teacher/SystemPromptView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'users',
        name: 'SchoolAdminUserManagement',
        component: () => import('@/views/teacher/UserManagementView.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'system-settings',
        name: 'SchoolAdminSystemSettings',
        component: () => import('@/views/teacher/SystemSettingsView.vue'),
      },
      {
        path: 'conversation/:id',
        name: 'SchoolAdminConversationDetail',
        component: () => import('@/views/teacher/ConversationDetailView.vue'),
      },
      {
        path: 'leads/:id',
        name: 'SchoolAdminLeadDetail',
        component: () => import('@/views/teacher/LeadDetailView.vue'),
      },
    ],
  },
  // 销售后台
  {
    path: '/expo-system/user',
    component: TeacherLayout,
    meta: { requiresAuth: true, roles: ['sales'] },
    children: [
      {
        path: '',
        name: 'TeacherPortalHome',
        component: () => import('@/views/teacher/DashboardView.vue'),
      },
      {
        path: 'leads',
        name: 'TeacherLeadList',
        component: () => import('@/views/teacher/LeadsView.vue'),
      },
      {
        path: 'manual-callbacks',
        name: 'TeacherManualCallbacks',
        component: () => import('@/views/teacher/ManualCallbacksView.vue'),
      },
      {
        path: 'knowledge-base',
        name: 'TeacherKnowledgeBase',
        component: () => import('@/views/teacher/KnowledgeBaseView.vue'),
      },
      {
        path: 'system-settings',
        name: 'TeacherSystemSettings',
        component: () => import('@/views/teacher/SystemSettingsView.vue'),
      },
      {
        path: 'conversation/:id',
        name: 'TeacherConversationDetail',
        component: () => import('@/views/teacher/ConversationDetailView.vue'),
      },
      {
        path: 'leads/:id',
        name: 'TeacherLeadDetail',
        component: () => import('@/views/teacher/LeadDetailView.vue'),
      },
    ],
  },
  // 家长端布局 (公开访问)
  {
    path: '/expoagent',
    component: ParentLayout,
    children: [
      {
        path: 'conversations/:id',
        name: 'ParentChat',
        component: () => import('@/views/parent/ChatView.vue'),
      },
    ]
  },
  // 404 Not Found
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 全局路由守卫
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore();
  if (!authStore.ensureValidSession()) {
    if (to.meta.requiresAuth) {
      next({ name: 'Login', query: { redirect: to.fullPath } });
      return;
    }
  }
  const savedLocale = getAppStorageItem('selectedLanguage');
  const supportedLocales = ['zh-CN', 'en', 'zh-TW', 'ja', 'ko', 'fr', 'es', 'ru'] as const;
  if (savedLocale && supportedLocales.includes(savedLocale as (typeof supportedLocales)[number]) && i18n.global.locale.value !== savedLocale) {
    i18n.global.locale.value = savedLocale as (typeof supportedLocales)[number];
  }
  const toRoles = to.meta.roles as string[] | undefined;
  const userRole = authStore.userRole;

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if (toRoles && toRoles.length > 0 && (!userRole || !toRoles.includes(userRole))) {
    console.warn(`Role mismatch: Required ${toRoles}, but user has ${authStore.userRole}`);
    if (authStore.isAuthenticated) {
      next(getPortalHomePath(userRole));
      return;
    }
    next({ name: 'NotFound' });
  } else {
    if (to.meta.requiresAuth && (userRole === 'super_admin' || userRole === 'admin' || userRole === 'sales')) {
      try {
        await useFeatureGateStore().fetchFeatureGates(true);
      } catch (error) {
        console.error('Failed to preload feature gates before route enter:', error);
      }
    }
    next();
  }
});

export default router;
