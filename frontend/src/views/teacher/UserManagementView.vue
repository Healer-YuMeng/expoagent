<template>
  <div class="user-mgmt">
    <header class="page-header">
      <div>
        <h1 class="title">{{ t('teacher.users.title') }}</h1>
        <p class="subtitle">{{ t('teacher.users.subtitle') }}</p>
      </div>
      <button class="primary" @click="createUser" :disabled="creating">
        {{ creating ? t('teacher.users.creating') : `➕ ${t('teacher.users.createAction')}` }}
      </button>
    </header>

    <section class="card">
      <div class="form-grid">
        <label>
          {{ t('teacher.users.accountLabel') }}
          <input v-model="form.phone" :placeholder="t('teacher.users.accountPlaceholder')" />
        </label>
        <label>
          {{ t('teacher.users.passwordLabel') }}
          <input v-model="form.password" type="password" :placeholder="t('teacher.users.passwordPlaceholder')" />
        </label>
        <label>
          {{ t('teacher.users.nameLabel') }}
          <input v-model="form.name" :placeholder="t('teacher.users.optionalPlaceholder')" />
        </label>
        <label>
          {{ t('teacher.users.emailLabel') }}
          <input v-model="form.email" :placeholder="t('teacher.users.optionalPlaceholder')" />
        </label>
        <template v-if="isSuperAdmin">
          <label>
            {{ t('teacher.users.schoolIdLabel') }}
            <input v-model="form.school_id" :placeholder="t('teacher.users.requiredPlaceholder')" />
          </label>
          <label>
            {{ t('teacher.users.schoolNameLabel') }}
            <input v-model="form.school_name" :placeholder="t('teacher.users.optionalPlaceholder')" />
          </label>
        </template>
        <div class="hint">{{ t('teacher.users.roleLabel') }}：{{ getRoleText(isSuperAdmin ? 'admin' : 'sales') }}</div>
      </div>
    </section>

    <section class="card">
      <div class="table-header">
        <h3>{{ t('teacher.users.createdAccounts') }}</h3>
        <span class="total">{{ t('teacher.users.totalCount', { count: users.length }) }}</span>
      </div>
      <table class="user-table" v-if="users.length">
        <thead>
          <tr>
            <th>{{ t('teacher.users.tableAccount') }}</th>
            <th>{{ t('teacher.users.tableName') }}</th>
            <th>{{ t('teacher.users.tableRole') }}</th>
            <th v-if="isSuperAdmin">{{ t('teacher.users.tableSchool') }}</th>
            <th>{{ t('teacher.users.tableStatus') }}</th>
            <th>{{ t('teacher.users.tableActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.phone }}</td>
            <td>{{ u.name || '-' }}</td>
            <td>{{ getRoleText(u.role) }}</td>
            <td v-if="isSuperAdmin">{{ u.school_name || u.school_id || '-' }}</td>
            <td>{{ u.is_active === false ? t('teacher.users.statusDisabled') : t('teacher.users.statusActive') }}</td>
            <td>
              <button class="danger" @click="removeUser(u.id)">{{ t('common.delete') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">{{ t('teacher.users.emptyState') }}</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '@/stores/auth';
import { listManagedUsers, createManagedUser, deleteManagedUser, type ManagedUser } from '@/api/teacher';
import { useI18n } from 'vue-i18n';

const authStore = useAuthStore();
const isSuperAdmin = computed(() => authStore.userRole === 'super_admin');
const { t } = useI18n();

const users = ref<ManagedUser[]>([]);
const creating = ref(false);
const form = ref({
  phone: '',
  password: '',
  name: '',
  email: '',
  school_id: '',
  school_name: '',
});

const getRoleText = (role: string) => {
  if (role === 'admin') {
    return t('teacher.users.roleSchoolAdmin');
  }
  return t('teacher.users.roleTeacher');
};

const fetchUsers = async () => {
  try {
    const res = await listManagedUsers();
    users.value = res.items || [];
  } catch (e) {
    console.error(e);
    ElMessage.error(t('teacher.users.loadError'));
  }
};

const createUser = async () => {
  if (!form.value.phone || !form.value.password) {
    ElMessage.warning(t('teacher.users.requiredWarning'));
    return;
  }
  if (isSuperAdmin.value && !form.value.school_id) {
    ElMessage.warning(t('teacher.users.schoolIdWarning'));
    return;
  }
  creating.value = true;
  try {
    await createManagedUser({
      phone: form.value.phone,
      password: form.value.password,
      role: isSuperAdmin.value ? 'admin' : 'sales',
      name: form.value.name || undefined,
      email: form.value.email || undefined,
      school_id: isSuperAdmin.value ? form.value.school_id : undefined,
      school_name: isSuperAdmin.value ? form.value.school_name : undefined,
    });
    ElMessage.success(t('teacher.users.createSuccess'));
    await fetchUsers();
  } catch (e: any) {
    console.error(e);
    const msg = e?.response?.data?.detail || t('teacher.users.createError');
    ElMessage.error(msg);
  } finally {
    creating.value = false;
  }
};

const removeUser = async (id: string) => {
  try {
    await deleteManagedUser(id);
    ElMessage.success(t('teacher.users.deleteSuccess'));
    await fetchUsers();
  } catch (e) {
    console.error(e);
    ElMessage.error(t('teacher.users.deleteError'));
  }
};

onMounted(() => {
  fetchUsers();
});
</script>

<style scoped>
.user-mgmt {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
}
.title { margin: 0; font-size: 22px; }
.subtitle { margin: 4px 0 0; color: #666; }
.primary {
  background: linear-gradient(135deg, #0077ff, #00c6ff);
  color: #fff;
  border: none;
  padding: 10px 16px;
  border-radius: 10px;
  cursor: pointer;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.05);
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px,1fr));
  gap: 12px;
}
label { display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
input {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px 10px;
}
.hint { color: #888; }
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.user-table { width: 100%; border-collapse: collapse; }
.user-table th, .user-table td {
  border: 1px solid #eee;
  padding: 8px 10px;
  text-align: left;
}
.danger {
  background: #fbe5e5;
  color: #c0392b;
  border: none;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
}
.empty { color: #888; }
</style>
