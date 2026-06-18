<template>
  <div class="paint-container">
    <!-- 蓝色颜料滴 - 从上方流下 -->
    <div 
      v-for="i in blueDropCount" 
      :key="`blue-${i}`"
      :class="`paint-drop blue-${i}`"
    ></div>
    
    <!-- 红色颜料滴 - 从下方流上 -->
    <div 
      v-for="i in redDropCount" 
      :key="`red-${i}`"
      :class="`paint-drop red-${i}`"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';

// 配置颜料滴数量
const blueDropCount = ref(6);
const redDropCount = ref(6);

// 页面加载时随机化颜料块位置
onMounted(() => {
  randomizePaintDrops();
});

function randomizePaintDrops() {
  // 获取所有蓝色颜料块
  const blueDrops = document.querySelectorAll('[class*="blue-"]');
  blueDrops.forEach(drop => {
    const randomLeft = Math.random() * 80 + 10; // 10-90%
    const randomTop = Math.random() * 40 - 20; // -20% 到 20%
    (drop as HTMLElement).style.left = randomLeft + '%';
    (drop as HTMLElement).style.top = randomTop + '%';
    (drop as HTMLElement).style.right = 'auto';
  });

  // 获取所有红色颜料块
  const redDrops = document.querySelectorAll('[class*="red-"]');
  redDrops.forEach(drop => {
    const randomLeft = Math.random() * 80 + 10; // 10-90%
    const randomBottom = Math.random() * 40 - 20; // -20% 到 20%
    (drop as HTMLElement).style.left = randomLeft + '%';
    (drop as HTMLElement).style.bottom = randomBottom + '%';
    (drop as HTMLElement).style.right = 'auto';
    (drop as HTMLElement).style.top = 'auto';
  });
}
</script>

<style scoped>
/* 颜料流动容器 */
.paint-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(to bottom, 
    rgba(255, 255, 255, 0) 0%, 
    rgba(255, 255, 255, 0.25) 30%,
    rgba(255, 255, 255, 0.9) 50%,
    rgba(255, 255, 255, 0.25) 70%,
    rgba(255, 255, 255, 0) 100%
  );
}

/* 颜料滴基础样式 */
.paint-drop {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.7;
  mix-blend-mode: multiply;
}

/* ==================== 蓝色颜料滴 ==================== */
.blue-1 {
  width: 800px;
  height: 600px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.9) 0%, 
    rgba(0, 61, 143, 0.7) 30%, 
    rgba(0, 61, 143, 0.5) 50%,
    transparent 80%);
  top: -280px;
  left: 5%;
  animation: blueDrip1 25s ease-in-out infinite;
}

.blue-2 {
  width: 350px;
  height: 280px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.85) 0%, 
    rgba(0, 61, 143, 0.65) 30%, 
    rgba(0, 61, 143, 0.45) 50%,
    transparent 80%);
  top: 10%;
  right: 8%;
  animation: blueDrip2 28s ease-in-out infinite;
}

.blue-3 {
  width: 650px;
  height: 480px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.8) 0%, 
    rgba(0, 61, 143, 0.6) 30%, 
    rgba(0, 61, 143, 0.4) 50%,
    transparent 80%);
  top: 25%;
  left: 65%;
  animation: blueDrip3 32s ease-in-out infinite;
}

.blue-4 {
  width: 420px;
  height: 320px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.75) 0%, 
    rgba(0, 61, 143, 0.55) 30%, 
    rgba(0, 61, 143, 0.35) 50%,
    transparent 80%);
  top: -150px;
  left: 38%;
  animation: blueDrip4 30s ease-in-out infinite;
}

.blue-5 {
  width: 280px;
  height: 220px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.8) 0%, 
    rgba(0, 61, 143, 0.6) 30%, 
    rgba(0, 61, 143, 0.4) 50%,
    transparent 80%);
  top: 15%;
  left: 22%;
  animation: blueDrip5 26s ease-in-out infinite;
}

.blue-6 {
  width: 950px;
  height: 680px;
  background: radial-gradient(ellipse at center, 
    rgba(0, 61, 143, 0.85) 0%, 
    rgba(0, 61, 143, 0.65) 30%, 
    rgba(0, 61, 143, 0.45) 50%,
    transparent 80%);
  top: -320px;
  right: 25%;
  animation: blueDrip6 34s ease-in-out infinite;
}

/* ==================== 深红色颜料滴 ==================== */
.red-1 {
  width: 720px;
  height: 550px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.9) 0%, 
    rgba(180, 13, 76, 0.7) 30%, 
    rgba(180, 13, 76, 0.5) 50%,
    transparent 80%);
  bottom: -250px;
  right: 3%;
  animation: redDrip1 27s ease-in-out infinite;
}

.red-2 {
  width: 380px;
  height: 300px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.85) 0%, 
    rgba(180, 13, 76, 0.65) 30%, 
    rgba(180, 13, 76, 0.45) 50%,
    transparent 80%);
  bottom: 8%;
  left: 12%;
  animation: redDrip2 29s ease-in-out infinite;
}

.red-3 {
  width: 850px;
  height: 620px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.8) 0%, 
    rgba(180, 13, 76, 0.6) 30%, 
    rgba(180, 13, 76, 0.4) 50%,
    transparent 80%);
  bottom: 20%;
  left: 58%;
  animation: redDrip3 33s ease-in-out infinite;
}

.red-4 {
  width: 450px;
  height: 340px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.75) 0%, 
    rgba(180, 13, 76, 0.55) 30%, 
    rgba(180, 13, 76, 0.35) 50%,
    transparent 80%);
  bottom: -180px;
  right: 42%;
  animation: redDrip4 31s ease-in-out infinite;
}

.red-5 {
  width: 320px;
  height: 260px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.82) 0%, 
    rgba(180, 13, 76, 0.62) 30%, 
    rgba(180, 13, 76, 0.42) 50%,
    transparent 80%);
  bottom: 12%;
  right: 28%;
  animation: redDrip5 28s ease-in-out infinite;
}

.red-6 {
  width: 920px;
  height: 700px;
  background: radial-gradient(ellipse at center, 
    rgba(180, 13, 76, 0.88) 0%, 
    rgba(180, 13, 76, 0.68) 30%, 
    rgba(180, 13, 76, 0.48) 50%,
    transparent 80%);
  bottom: -280px;
  left: 35%;
  animation: redDrip6 35s ease-in-out infinite;
}

/* ==================== 蓝色颜料流动动画 ==================== */
@keyframes blueDrip1 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  25% {
    transform: translate(-180px, 220px) rotate(12deg) scale(1.08);
  }
  50% {
    transform: translate(120px, 350px) rotate(-15deg) scale(1.15);
  }
  75% {
    transform: translate(-80px, 180px) rotate(8deg) scale(1.05);
  }
}

@keyframes blueDrip2 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  20% {
    transform: translate(-350px, -80px) rotate(-25deg) scale(1.2);
  }
  40% {
    transform: translate(280px, 150px) rotate(18deg) scale(0.95);
  }
  60% {
    transform: translate(-180px, 80px) rotate(-12deg) scale(1.15);
  }
  80% {
    transform: translate(220px, -50px) rotate(22deg) scale(1.08);
  }
}

@keyframes blueDrip3 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  30% {
    transform: translate(-220px, -120px) rotate(16deg) scale(1.1);
  }
  60% {
    transform: translate(180px, 200px) rotate(-20deg) scale(1.12);
  }
}

@keyframes blueDrip4 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  15% {
    transform: translate(320px, 180px) rotate(-28deg) scale(1.25);
  }
  35% {
    transform: translate(-280px, -120px) rotate(15deg) scale(0.92);
  }
  55% {
    transform: translate(180px, 250px) rotate(-18deg) scale(1.18);
  }
  75% {
    transform: translate(-150px, 80px) rotate(20deg) scale(1.05);
  }
}

@keyframes blueDrip5 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  16% {
    transform: translate(420px, -90px) rotate(32deg) scale(1.3);
  }
  36% {
    transform: translate(-180px, 200px) rotate(-24deg) scale(0.85);
  }
  56% {
    transform: translate(320px, 120px) rotate(28deg) scale(1.22);
  }
  76% {
    transform: translate(-220px, -50px) rotate(-20deg) scale(0.95);
  }
}

@keyframes blueDrip6 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  28% {
    transform: translate(-200px, 280px) rotate(14deg) scale(1.08);
  }
  56% {
    transform: translate(150px, 180px) rotate(-18deg) scale(1.12);
  }
}

/* ==================== 红色颜料流动动画 ==================== */
@keyframes redDrip1 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  30% {
    transform: translate(150px, -250px) rotate(-16deg) scale(1.1);
  }
  60% {
    transform: translate(-120px, -180px) rotate(14deg) scale(1.12);
  }
}

@keyframes redDrip2 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  18% {
    transform: translate(380px, 120px) rotate(26deg) scale(1.22);
  }
  38% {
    transform: translate(-220px, -150px) rotate(-18deg) scale(0.93);
  }
  58% {
    transform: translate(280px, 80px) rotate(20deg) scale(1.18);
  }
  78% {
    transform: translate(-180px, -80px) rotate(-15deg) scale(1.08);
  }
}

@keyframes redDrip3 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  25% {
    transform: translate(-200px, 150px) rotate(18deg) scale(1.08);
  }
  50% {
    transform: translate(180px, -220px) rotate(-22deg) scale(1.14);
  }
  75% {
    transform: translate(-100px, -120px) rotate(12deg) scale(1.06);
  }
}

@keyframes redDrip4 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  22% {
    transform: translate(-350px, -100px) rotate(-30deg) scale(1.28);
  }
  44% {
    transform: translate(250px, 180px) rotate(22deg) scale(0.88);
  }
  66% {
    transform: translate(-280px, -180px) rotate(-25deg) scale(1.2);
  }
  88% {
    transform: translate(180px, 100px) rotate(18deg) scale(1.1);
  }
}

@keyframes redDrip5 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  20% {
    transform: translate(-380px, 100px) rotate(-28deg) scale(1.26);
  }
  40% {
    transform: translate(280px, -180px) rotate(22deg) scale(0.9);
  }
  60% {
    transform: translate(-250px, 150px) rotate(-24deg) scale(1.2);
  }
  80% {
    transform: translate(200px, -100px) rotate(18deg) scale(1.05);
  }
}

@keyframes redDrip6 {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  26% {
    transform: translate(180px, -200px) rotate(15deg) scale(1.1);
  }
  52% {
    transform: translate(-150px, -280px) rotate(-20deg) scale(1.14);
  }
  78% {
    transform: translate(120px, -180px) rotate(12deg) scale(1.06);
  }
}

/* ==================== 响应式设计 ==================== */
@media (max-width: 768px) {
  .paint-drop {
    filter: blur(40px);
  }
}
</style>

