import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import TeacherLayout from '@/components/TeacherLayout.vue';
import ParentLayout from '@/components/ParentLayout.vue';
import i18n from '@/i18n';
import { getAppStorageItem } from '@/utils/browserStorage';

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
  // 后台布局
  {
    path: '/teacher',
    component: TeacherLayout,
    meta: { requiresAuth: true, roles: ['teacher', 'school_admin', 'super_admin'] },
    redirect: '/teacher/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/teacher/DashboardView.vue'),
      },
      {
        path: 'leads',
        name: 'LeadList',
        component: () => import('@/views/teacher/LeadsView.vue'),
      },
      {
        path: 'manual-callbacks',
        name: 'ManualCallbacks',
        component: () => import('@/views/teacher/ManualCallbacksView.vue'),
      },
      {
        path: 'knowledge-base',
        name: 'KnowledgeBase',
        component: () => import('@/views/teacher/KnowledgeBaseView.vue'),
        meta: { roles: ['school_admin'] },
      },
      {
        path: 'system-prompt',
        name: 'SystemPrompt',
        component: () => import('@/views/teacher/SystemPromptView.vue'),
        meta: { roles: ['school_admin', 'super_admin'] },
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('@/views/teacher/UserManagementView.vue'),
        meta: { roles: ['school_admin', 'super_admin'] },
      },
      {
        path: 'system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/teacher/SystemSettingsView.vue'),
      },
      {
        path: 'conversation/:id',
        name: 'TeacherConversation',
        component: () => import('@/views/teacher/ConversationDetailView.vue'),
      },
      {
        path: 'leads/:id',
        name: 'LeadDetail',
        component: () => import('@/views/teacher/LeadDetailView.vue'),
      },
    ]
  },
  // 家长端布局 (公开访问)
  {
    path: '/parent',
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
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore();
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
    next({ name: 'NotFound' });
  } else {
    next();
  }
});

export default router;
