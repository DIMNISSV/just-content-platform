<script setup>
import {ref, computed} from 'vue';

const props = defineProps({
  contentTree: {type: Array, required: true}
});

const emit = defineEmits(['assign-drop']);

const searchQuery = ref('');
const expandedTitles = ref(new Set());
const expandedEpisodes = ref(new Set());

const filteredTree = computed(() => {
  if (!searchQuery.value.trim()) return props.contentTree;
  const q = searchQuery.value.toLowerCase();
  return props.contentTree.filter(t =>
      t.name.toLowerCase().includes(q) ||
      (t.original_name && t.original_name.toLowerCase().includes(q))
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
</script>

<template>
  <div class="w-2/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
    <div class="p-4 border-b border-gray-800 bg-black/20 space-y-3">
      <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Content Library</h3>
      <input v-model="searchQuery" type="text" placeholder="Search titles by name..."
             class="w-full bg-black border border-gray-700 rounded p-2 text-xs text-white focus:border-brand outline-none transition-colors"/>
    </div>

    <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
      <div v-if="filteredTree.length === 0" class="text-center text-sm text-gray-500 py-10">
        No titles found matching "{{ searchQuery }}"
      </div>

      <div v-for="title in filteredTree" :key="title.id" class="mb-4">
        <div @click="toggleTitle(title.id)"
             class="flex items-center gap-3 p-2 hover:bg-gray-800 rounded cursor-pointer transition-colors bg-gray-800/30">
          <svg class="w-4 h-4 transition-transform text-gray-400" :class="{'rotate-90': expandedTitles.has(title.id)}"
               fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
          <span class="font-bold text-lg">{{ title.name }}</span>
          <span class="text-[10px] uppercase border border-gray-700 px-1.5 rounded text-gray-500">{{
              title.type
            }}</span>
        </div>

        <div v-if="expandedTitles.has(title.id)" class="ml-6 mt-2 space-y-2 border-l-2 border-gray-800 pl-4">
          <div v-for="ep in title.episodes" :key="ep.id" class="border border-gray-800 rounded-lg overflow-hidden">
            <div @click="toggleEpisode(ep.id)"
                 class="p-3 text-sm font-bold text-gray-300 hover:bg-gray-800 cursor-pointer flex justify-between bg-black/20">
              <span>S{{ ep.season_number }}E{{ ep.episode_number }}: {{ ep.name || 'Episode' }}</span>
              <span class="text-[10px] text-gray-500 bg-gray-900 px-2 py-0.5 rounded border border-gray-700">{{
                  ep.track_groups?.length || 0
                }} Versions</span>
            </div>

            <div v-if="expandedEpisodes.has(ep.id)" class="p-3 space-y-3 bg-gray-900/50">
              <div v-for="group in ep.track_groups" :key="group.id"
                   @dragover.prevent @drop="handleDrop($event, group.id, 'existing_group', 'track_group', group.name)"
                   class="p-3 border border-gray-700 rounded bg-gray-800/50 hover:border-blue-500 transition-colors border-dashed relative group/dropzone">
                <div
                    class="absolute inset-0 bg-blue-500/10 opacity-0 group-hover/dropzone:opacity-100 transition-opacity pointer-events-none"></div>
                <div class="text-xs font-black uppercase text-gray-400 mb-2 flex justify-between">
                  {{ group.name }}
                  <span class="text-blue-400 opacity-0 group-hover/dropzone:opacity-100 text-[10px]">Drop to add Audio/Subtitles</span>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span v-for="asset in group.assets" :key="asset.id"
                        class="text-[10px] font-bold px-2 py-1 rounded border"
                        :class="asset.type === 'VIDEO' ? 'bg-blue-900/30 text-blue-300 border-blue-800' : 'bg-green-900/30 text-green-300 border-green-800'">
                    {{ asset.type }}: {{ asset.name }}
                  </span>
                </div>
              </div>

              <div @dragover.prevent
                   @drop="handleDrop($event, ep.id, 'new_group', 'episode', 'New Version for S' + ep.season_number + 'E' + ep.episode_number)"
                   class="p-4 border-2 border-dashed border-gray-700 rounded text-center text-xs font-bold text-gray-500 hover:border-brand hover:text-brand hover:bg-brand/5 transition-all cursor-pointer">
                + DROP VIDEO HERE TO CREATE A NEW VERSION
              </div>
            </div>
          </div>
          <div v-if="title.episodes.length === 0" class="text-xs text-gray-600 italic p-2">No episodes created yet.
          </div>
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