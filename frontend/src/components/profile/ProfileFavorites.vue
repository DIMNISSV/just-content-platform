<script setup>
defineProps({
  favorites: {type: Array, required: true}
});
</script>

<template>
  <section>
    <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-brand pl-3">Мой список</h2>
    <div v-if="favorites.length === 0" class="text-gray-500 text-sm">Ваш список пуст.</div>
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
      <a v-for="title in favorites" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
        <div
            class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative border border-gray-800 hover:border-brand transition">
          <img v-if="title.poster" :src="title.poster" :alt="title.name"
               class="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300">
          <div class="absolute top-2 right-2 bg-brand px-2 py-1 rounded text-xs font-bold text-white">*
            {{ Number(title.rating_score).toFixed(1) }}
          </div>
        </div>
        <h3 class="text-sm font-semibold truncate text-gray-200 group-hover:text-white">{{ title.name }}</h3>

        <div class="flex flex-wrap gap-1 mt-1.5 h-4 overflow-hidden">
          <span v-for="t in (title.taxonomy_items || []).filter(i => i.type !== 'TYPE').slice(0, 3)" :key="t.id"
                class="text-[9px] uppercase font-bold border border-gray-700 px-1 rounded truncate max-w-[80px]"
                :class="{
                  'text-blue-400': t.type === 'GENRE',
                  'text-green-400': t.type === 'TAG',
                  'text-purple-400': t.type === 'CATEGORY'
                }">
            {{ t.name }}
          </span>
        </div>
      </a>
    </div>
  </section>
</template>