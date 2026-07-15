<script setup>
defineProps({
  history: {type: Array, required: true}
});

const formatTime = (ms) => {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const getWatchLink = (item) => {
  return item.episode ? `/watch/episode/${item.episode.id}/` : `/watch/${item.title.id}/`;
};
</script>

<template>
  <section>
    <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-gray-600 pl-3">История просмотров</h2>
    <div v-if="history.length === 0" class="text-gray-500 text-sm">История просмотров пока пуста.</div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      <a v-for="item in history" :key="item.id" :href="getWatchLink(item)"
         class="group bg-gray-900 rounded-lg overflow-hidden border border-gray-800 hover:border-brand transition block">
        <div class="aspect-video relative bg-black">
          <img v-if="item.title.poster" :src="item.title.poster"
               class="w-full h-full object-cover opacity-50 group-hover:opacity-70 transition-opacity">
          <div class="absolute bottom-2 right-2 bg-black/80 px-2 py-1 rounded text-xs font-bold text-white">
            {{ formatTime(item.progress_ms) }}
          </div>
        </div>
        <div class="p-4">
          <h3 class="text-sm font-bold text-white truncate">{{ item.title.name }}</h3>
          <p class="text-xs text-gray-400 mt-1 truncate">
            <template v-if="item.episode">Сезон {{ item.episode.season_number }} Серия {{
                item.episode.episode_number
              }}
            </template>
            <template v-else>Фильм</template>
          </p>
        </div>
      </a>
    </div>
  </section>
</template>