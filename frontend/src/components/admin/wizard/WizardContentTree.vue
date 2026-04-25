<script setup>
import {computed, ref} from 'vue';

const props = defineProps({
  contentTree: {type: Array, required: true}
});

const emit = defineEmits(['assign-drop', 'create-episode', 'delete-group', 'delete-track']);

const searchQuery = ref('');
const expandedTitles = ref(new Set());
const expandedEpisodes = ref(new Set());

const filteredTree = computed(() => {
  if (!searchQuery.value.trim()) return props.contentTree;
  const q = searchQuery.value.toLowerCase();
  return props.contentTree.filter(t =>
      t.name.toLowerCase().includes(q) || (t.original_name && t.original_name.toLowerCase().includes(q))
  );
});

const toggleTitle = (id) => {
  if (expandedTitles.value.has(id)) expandedTitles.value.delete(id);
  else expandedTitles.value.add(id);
};

const toggleEpisode = (id) => {
  if (expandedEpisodes.value.has(id)) expandedEpisodes.value.delete(id);
  else expandedEpisodes.value.add(id);
};

const handleDrop = (e, targetId, dropType, targetType, targetName) => {
  e.preventDefault();
  const fileId = e.dataTransfer.getData('fileId');
  if (fileId) {
    emit('assign-drop', {fileId, targetId, dropType, targetType, targetName});
  }
};

const promptCreateEpisode = (titleId) => {
  const season = prompt("Season Number:", "1");
  const number = prompt("Episode Number:", "1");
  const name = prompt("Episode Name (Optional):", "");
  if (season && number) {
    emit('create-episode', {title: titleId, season_number: parseInt(season), episode_number: parseInt(number), name});
  }
};
</script>

<template>
  <div class="w-2/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
    <div class="p-4 border-b border-gray-800 bg-black/20 space-y-3">
      <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Content Library</h3>
      <input v-model="searchQuery" type="text" placeholder="Search titles..."
             class="w-full bg-black border border-gray-700 rounded p-2 text-xs text-white focus:border-brand outline-none"/>
    </div>

    <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
      <div v-for="title in filteredTree" :key="title.id" class="mb-4">

        <!-- Уровень Тайтла -->
        <div class="flex items-center justify-between group/title bg-gray-800/30 rounded pr-2 mb-1">
          <div @click="toggleTitle(title.id)" class="flex items-center gap-3 p-2 cursor-pointer flex-grow">
            <svg class="w-4 h-4 transition-transform text-gray-400" :class="{'rotate-90': expandedTitles.has(title.id)}"
                 fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="font-bold text-lg">{{ title.name }}</span>
            <span class="text-[10px] uppercase border border-gray-700 px-1.5 rounded text-gray-500">{{
                title.type
              }}</span>
          </div>
          <button v-if="title.type === 'SERIES'" @click.stop="promptCreateEpisode(title.id)"
                  class="opacity-0 group-hover/title:opacity-100 bg-gray-700 hover:bg-brand text-[10px] px-2 py-1 rounded font-bold transition-all">
            + ADD EPISODE
          </button>
        </div>

        <!-- Контент внутри Тайтла -->
        <div v-if="expandedTitles.has(title.id)" class="ml-6 mt-2 space-y-2 border-l-2 border-gray-800 pl-4">

          <!-- ЕСЛИ ЭТО ФИЛЬМ: Выводим версии напрямую -->
          <template v-if="title.type === 'MOVIE'">
            <div class="p-3 space-y-3 bg-gray-900/50 rounded-lg">
              <div v-for="group in title.track_groups" :key="group.id"
                   @dragover.prevent @drop="handleDrop($event, group.id, 'existing_group', 'track_group', group.name)"
                   class="p-3 border border-gray-700 rounded bg-gray-800/50 hover:border-blue-500 transition-colors border-dashed relative group/version">

                <div class="text-xs font-black uppercase text-gray-400 mb-2 flex justify-between items-center">
                  <div class="flex items-center gap-2">
                    <span>{{ group.name }}</span>
                    <span v-if="group.author"
                          class="text-[9px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/30">
                      {{ group.author }}
                    </span>
                  </div>
                  <button @click="emit('delete-group', group.id)"
                          class="opacity-0 group-hover/version:opacity-100 text-gray-500 hover:text-brand transition-opacity">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </div>

                <div class="flex flex-wrap gap-2">
                  <div v-for="asset in group.assets" :key="asset.id"
                       class="text-[10px] font-bold px-2 py-1 rounded border flex items-center gap-1.5"
                       :class="asset.type === 'VIDEO' ? 'bg-blue-900/30 text-blue-300 border-blue-800' : 'bg-green-900/30 text-green-300 border-green-800 group/asset'">
                    <span class="opacity-70">{{ asset.type }}:</span>
                    <span>{{ asset.author || 'Original' }}</span>
                    <span class="text-[9px] font-mono opacity-60">({{ asset.name.toUpperCase() }})</span>
                    <button v-if="asset.type !== 'VIDEO'" @click="emit('delete-track', asset.link_id)"
                            class="opacity-0 group-hover/asset:opacity-100 hover:text-white text-green-600">×
                    </button>
                  </div>
                </div>
              </div>
              <div @dragover.prevent @drop="handleDrop($event, title.id, 'new_group', 'title', 'New Version')"
                   class="p-4 border-2 border-dashed border-gray-700 rounded text-center text-xs font-bold text-gray-500 hover:border-brand hover:text-brand transition-all cursor-pointer">
                + DROP VIDEO FOR NEW MOVIE VERSION
              </div>
            </div>
          </template>

          <template v-else>
            <div v-for="ep in title.episodes" :key="ep.id" class="border border-gray-800 rounded-lg overflow-hidden">
              <div @click="toggleEpisode(ep.id)"
                   class="p-3 text-sm font-bold text-gray-300 hover:bg-gray-800 cursor-pointer flex justify-between bg-black/20">
                <span>S{{ ep.season_number }}E{{ ep.episode_number }}: {{ ep.name || 'Episode' }}</span>
                <span class="text-[10px] text-gray-500">{{ ep.track_groups?.length || 0 }} Versions</span>
              </div>

              <div v-if="expandedEpisodes.has(ep.id)" class="p-3 space-y-3 bg-gray-900/50">
                <div v-for="group in ep.track_groups" :key="group.id"
                     @dragover.prevent @drop="handleDrop($event, group.id, 'existing_group', 'track_group', group.name)"
                     class="p-3 border border-gray-700 rounded bg-gray-800/50 hover:border-blue-500 transition-colors border-dashed relative group/version">
                  <div class="text-xs font-black uppercase text-gray-400 mb-2 flex justify-between items-center">
                    <span>{{ group.name }}</span>
                    <button @click="emit('delete-group', group.id)"
                            class="opacity-0 group-hover/version:opacity-100 text-gray-500 hover:text-brand transition-opacity">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                      </svg>
                    </button>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <div v-for="asset in group.assets" :key="asset.id"
                         class="text-[10px] font-bold px-2 py-1 rounded border flex items-center gap-1.5"
                         :class="asset.type === 'VIDEO' ? 'bg-blue-900/30 text-blue-300 border-blue-800' : 'bg-green-900/30 text-green-300 border-green-800 group/asset'">
                      {{ asset.type }}: {{ asset.name }}
                      <button v-if="asset.type !== 'VIDEO'" @click="emit('delete-track', asset.link_id)"
                              class="opacity-0 group-hover/asset:opacity-100 hover:text-white text-green-600">×
                      </button>
                    </div>
                  </div>
                </div>
                <div @dragover.prevent @drop="handleDrop($event, ep.id, 'new_group', 'episode', 'New Version')"
                     class="p-4 border-2 border-dashed border-gray-700 rounded text-center text-xs font-bold text-gray-500 hover:border-brand hover:text-brand hover:bg-brand/5 transition-all cursor-pointer group/zone">
                  <div class="flex flex-col items-center gap-1">
                    <svg class="w-5 h-5 text-gray-600 group-hover/zone:text-brand" fill="none" stroke="currentColor"
                         viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                    </svg>
                    <span>CREATE NEW VERSION (VIDEO REQUIRED)</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="title.episodes.length === 0" class="text-xs text-gray-600 italic p-2">No episodes created yet.
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 10px;
}
</style>