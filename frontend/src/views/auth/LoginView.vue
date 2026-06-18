<template>
  <div class="login-page">
    <!-- 背景动画组件 -->
    <PaintBackground />

    <!-- 主要内容区域 -->
    <div class="login-container">
      <!-- 返回首页按钮 -->
      <router-link to="/" class="back-home glass">← {{ t('common.backToHome') }}</router-link>

      <!-- 登录卡片 -->
      <div class="login-card card-ycis fade-in">
        <h1 class="login-title text-shadow-light">{{ t('login.welcome') }}</h1>
        <p class="login-subtitle">{{ t('login.subtitle') }}</p>

        <!-- 错误提示 -->
        <div v-if="errorMessage" class="error-message shake">
          {{ errorMessage }}
        </div>

        <!-- 登录表单 -->
        <el-form 
          ref="loginFormRef" 
          :model="loginForm" 
          :rules="loginRules" 
          @submit.prevent="handleLogin"
          class="login-form"
        >
          <!-- 手机号输入 -->
          <el-form-item prop="phone" class="form-group">
            <label class="form-label">{{ t('login.phone') }}</label>
            <el-input
              v-model="loginForm.phone"
              :placeholder="t('login.phonePlaceholder')"
              size="large"
              class="input-ycis"
              autocomplete="username"
            />
          </el-form-item>

          <!-- 密码输入 -->
          <el-form-item prop="password" class="form-group">
            <label class="form-label">{{ t('login.password') }}</label>
            <el-input
              v-model="loginForm.password"
              type="password"
              :placeholder="t('login.passwordPlaceholder')"
              size="large"
              show-password
              class="input-ycis"
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <!-- 记住我和忘记密码 -->
          <div class="remember-forgot">
            <label class="remember-me">
              <input v-model="rememberMe" type="checkbox" />
              <span>{{ t('login.rememberMe') }}</span>
            </label>
            <a href="#" class="forgot-password" @click.prevent="handleForgotPassword">
              {{ t('login.forgotPassword') }}
            </a>
          </div>

          <!-- 登录按钮 -->
          <el-form-item class="form-group">
            <button
              type="button"
              :disabled="loading"
              @click="handleLogin"
              class="login-btn btn-ycis btn-ycis-blue"
            >
              {{ loading ? t('login.loggingIn') : t('login.loginButton') }}
            </button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '@/stores/auth';
import { useI18n } from 'vue-i18n';
import PaintBackground from '@/components/PaintBackground.vue';

const authStore = useAuthStore();
const { t } = useI18n();

const loginFormRef = ref<FormInstance>();
const loginForm = ref({
  phone: '',
  password: '',
});
const loading = ref(false);
const rememberMe = ref(false);
const errorMessage = ref('');

const loginRules = computed<FormRules>(() => ({
  phone: [
    { required: true, message: t('login.phoneRequired'), trigger: 'blur' },
    { pattern: /^(admin|root|1[3-9]\d{9})$/, message: t('login.phoneInvalid'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('login.passwordRequired'), trigger: 'blur' },
    { min: 3, message: t('login.passwordMinLength'), trigger: 'blur' }
  ],
}));

const handleLogin = async () => {
  if (!loginFormRef.value) return;
  
  // 清除之前的错误提示
  errorMessage.value = '';
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true;
      try {
        await authStore.login(loginForm.value);
        ElMessage.success(t('login.loginSuccess'));
        // 路由跳转由 authStore 内部处理
      } catch (error: any) {
        const message = error?.response?.data?.detail || t('login.loginError');
        errorMessage.value = message;
        ElMessage.error(message);
        console.error(error);
      } finally {
        loading.value = false;
      }
    }
  });
};

const handleForgotPassword = () => {
  ElMessage.info(t('login.forgotPasswordInfo'));
};

// 自动聚焦到手机号输入框
onMounted(() => {
  // 延迟一下让动画完成
  setTimeout(() => {
    const phoneInput = document.querySelector('.input-ycis input') as HTMLInputElement;
    if (phoneInput) {
      phoneInput.focus();
    }
  }, 300);
});
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.login-page {
  min-height: 100vh;
  position: relative;
  background: #ffffff;
}

.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  position: relative;
  z-index: 10;
}

/* ==================== 返回首页按钮 ==================== */
.back-home {
  position: absolute;
  top: 30px;
  left: 30px;
  padding: 12px 24px;
  border-radius: var(--radius-full);
  color: var(--text-primary);
  text-decoration: none;
  font-weight: 500;
  font-size: 16px;
  transition: all 0.3s ease;
  box-shadow: var(--shadow-md);
}

.back-home:hover {
  background: rgba(255, 255, 255, 0.5);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

/* ==================== 登录卡片 ==================== */
.login-card {
  width: 90%;
  max-width: 500px;
  padding: 40px 35px !important;
}

/* ==================== 标题 ==================== */
.login-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  text-align: center;
  margin-bottom: 10px;
  text-shadow: 0 2px 10px rgba(255, 255, 255, 0.8);
}

.login-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  text-align: center;
  margin-bottom: 35px;
}

/* ==================== 表单 ==================== */
.login-form {
  width: 100%;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  padding-left: 5px;
}

/* ==================== Element Plus 组件样式覆盖 ==================== */
/* 移除 input-ycis 全局类的样式，避免双层效果 */
:deep(.el-input.input-ycis) {
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}

/* 让 Element Plus 的输入框使用我们的样式 - 单层设计，带边框 */
:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.5);
  border: 2px solid rgba(44, 62, 80, 0.25);
  border-radius: 15px;
  padding: 14px 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  background: rgba(255, 255, 255, 0.6);
}

:deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.7);
  border-color: rgba(0, 61, 143, 0.5);
  box-shadow: 0 0 0 4px rgba(0, 61, 143, 0.1), 0 2px 8px rgba(0, 0, 0, 0.08);
}

:deep(.el-input__inner) {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 400;
}

:deep(.el-input__inner::placeholder) {
  color: rgba(44, 62, 80, 0.5);
}

/* 隐藏 Element Plus 的表单项错误提示，使用我们自己的样式 */
:deep(.el-form-item__error) {
  display: none;
}

/* ==================== 记住我 ==================== */
.remember-forgot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  font-size: 14px;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.remember-me input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--ycis-blue);
}

.forgot-password {
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.3s ease;
}

.forgot-password:hover {
  color: var(--ycis-blue);
}

/* ==================== 登录按钮 ==================== */
.login-btn {
  width: 100%;
  padding: 16px;
  font-size: 18px;
  font-weight: 700;
  border-radius: 15px;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none !important;
}

/* ==================== 错误提示 ==================== */
.error-message {
  background: rgba(180, 13, 76, 0.15);
  border: 1px solid rgba(180, 13, 76, 0.3);
  color: var(--ycis-red);
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  margin-bottom: 20px;
  font-size: 14px;
  text-align: center;
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 768px) {
  .login-card {
    padding: 40px 30px !important;
  }

  .login-title {
    font-size: 28px;
  }

  .back-home {
    top: 20px;
    left: 20px;
    padding: 10px 20px;
    font-size: 14px;
  }
}
</style>
