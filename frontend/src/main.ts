import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

// 引入全局主题样式
import './styles/ycis-theme.css';

// 引入 i18n
import i18n from './i18n';

import App from './App.vue';
import router from './router';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.use(i18n);

app.mount('#app');
