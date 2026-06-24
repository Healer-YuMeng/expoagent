<template>
  <div class="paint-container" aria-hidden="true">
    <div class="base-gradient"></div>
    <div class="glow glow-primary"></div>
    <div class="glow glow-secondary"></div>
    <div class="glow glow-accent"></div>
    <div class="texture texture-grid"></div>
    <div class="texture texture-haze"></div>
  </div>
</template>

<style scoped>
.paint-container {
  position: fixed;
  inset: 0;
  z-index: 1;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 30%),
    linear-gradient(135deg, #f5f8fc 0%, #e8eff8 34%, #d6e2f0 100%);
}

.base-gradient,
.glow,
.texture {
  position: absolute;
  inset: 0;
}

.base-gradient {
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 255, 255, 0.72), transparent 22%),
    radial-gradient(circle at 78% 16%, rgba(88, 126, 184, 0.28), transparent 28%),
    radial-gradient(circle at 15% 84%, rgba(179, 196, 219, 0.34), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(194, 208, 226, 0.18));
}

.glow {
  border-radius: 999px;
  filter: blur(72px);
  opacity: 0.9;
}

.glow-primary {
  top: -8%;
  left: 46%;
  width: 46vw;
  height: 46vw;
  min-width: 420px;
  min-height: 420px;
  background: radial-gradient(circle, rgba(88, 129, 193, 0.5) 0%, rgba(88, 129, 193, 0.22) 42%, transparent 74%);
  animation: driftPrimary 20s ease-in-out infinite;
}

.glow-secondary {
  top: 24%;
  right: -10%;
  width: 52vw;
  height: 52vw;
  min-width: 460px;
  min-height: 460px;
  background: radial-gradient(circle, rgba(55, 88, 142, 0.42) 0%, rgba(55, 88, 142, 0.18) 46%, transparent 78%);
  animation: driftSecondary 24s ease-in-out infinite;
}

.glow-accent {
  bottom: -16%;
  left: -6%;
  width: 42vw;
  height: 42vw;
  min-width: 360px;
  min-height: 360px;
  background: radial-gradient(circle, rgba(216, 226, 239, 0.96) 0%, rgba(216, 226, 239, 0.34) 48%, transparent 82%);
  animation: driftAccent 26s ease-in-out infinite;
}

.texture-grid {
  opacity: 0.28;
  background-image:
    linear-gradient(rgba(119, 141, 171, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(119, 141, 171, 0.08) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.16), rgba(0, 0, 0, 0));
}

.texture-haze {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.12), transparent 28%),
    linear-gradient(0deg, rgba(230, 236, 244, 0.2), transparent 34%);
}

@keyframes driftPrimary {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-4%, 5%, 0) scale(1.05);
  }
}

@keyframes driftSecondary {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-5%, -4%, 0) scale(1.04);
  }
}

@keyframes driftAccent {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(5%, -3%, 0) scale(1.03);
  }
}

@media (max-width: 768px) {
  .glow {
    filter: blur(56px);
  }

  .texture-grid {
    background-size: 44px 44px;
    opacity: 0.2;
  }
}

@media (prefers-reduced-motion: reduce) {
  .glow-primary,
  .glow-secondary,
  .glow-accent {
    animation: none;
  }
}
</style>
