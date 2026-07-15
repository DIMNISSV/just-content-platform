<script setup>
import {ref, computed} from 'vue';

const props = defineProps({
  taxonomyItems: {type: Array, required: true},
  mappings: {type: Array, required: true}
});

const emit = defineEmits(['dropped', 'remove-mapping']);

const tabs = ['GENRE', 'TAG', 'TYPE', 'CATEGORY'];
const activeTab = ref('GENRE');
const dragOverId = ref(null);

const flattenTree = (roots, depth = 0) => {
  let result = [];
  roots.forEach(node => {
    result.push({...node, depth});
    if (node.children && node.children.length) {
      result = result.concat(flattenTree(node.children, depth + 1));
    }
  });
  return result;
};

const activeTree = computed(() => {
  const typeItems = props.taxonomyItems.filter(i => i.type === activeTab.value);
  const map = {};
  const roots = [];

  typeItems.forEach(i => {
    map[i.id] = {...i, children: [], mappedTerms: []};
  });

  props.mappings.forEach(m => {
    if (map[m.taxonomy_item]) {
      map[m.taxonomy_item].mappedTerms.push(m);
    }
  });

  typeItems.forEach(i => {
    if (i.parent && map[i.parent]) {
      map[i.parent].children.push(map[i.id]);
    } else {
      roots.push(map[i.id]);
    }
  });

  return flattenTree(roots);
});

const onDrop = (e, taxItem) => {
  dragOverId.value = null;
  const termId = e.dataTransfer.getData('termId');
  if (!termId) return;
  emit('dropped', {termId, taxonomyItemId: taxItem.id});
};
</script>

<template>
  <div class="col-span-2 bg-card rounded-lg border border-gray-800 flex flex-col overflow-hidden shadow">
    <div class="flex border-b border-gray-800 bg-gray-900 flex-shrink-0 overflow-x-auto">
      <button
          v-for="tab in tabs"
          :key="tab"
          @click="activeTab = tab"
          :class="['px-6 py-4 text-sm font-bold uppercase tracking-wider transition-colors border-b-2 whitespace-nowrap', activeTab === tab ? 'text-brand border-brand bg-gray-800' : 'text-gray-500 border-transparent hover:text-gray-300']"
      >
        <template v-if="tab === 'GENRE'">Жанр</template>
        <template v-else-if="tab === 'TAG'">Тег</template>
        <template v-else-if="tab === 'TYPE'">Тип</template>
        <template v-else-if="tab === 'CATEGORY'">Категория</template>
        <template v-else>{{ tab }}</template>
      </button>
    </div>

    <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
      <div v-if="activeTree.length === 0" class="text-gray-500 text-sm text-center py-4">
        Элементы таксономии для этой категории не найдены.
      </div>
      <div class="space-y-2">
        <div
            v-for="node in activeTree"
            :key="node.id"
            @dragover.prevent="dragOverId = node.id"
            @dragleave.prevent="dragOverId = null"
            @drop="onDrop($event, node)"
            :class="['p-4 rounded border transition-all duration-200', dragOverId === node.id ? 'border-brand bg-gray-800 scale-[1.01]' : 'border-gray-700 bg-black']"
            :style="{ marginLeft: node.depth * 24 + 'px' }"
        >
          <div class="flex justify-between items-start mb-2">
            <div>
              <h5 class="text-base font-bold text-white flex items-center gap-2">
                <svg v-if="node.depth > 0" class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor"
                     viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
                {{ node.name }}
              </h5>
              <p class="text-xs text-gray-500 mt-1">{{ node.slug }}</p>
            </div>
          </div>

          <div class="flex flex-wrap gap-2 mt-3" v-if="node.mappedTerms && node.mappedTerms.length > 0">
            <span
                v-for="mapping in node.mappedTerms"
                :key="mapping.id"
                class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-800 border border-gray-600 text-xs font-semibold text-gray-300"
            >
              {{ mapping.raw_term_name }}
              <button @click="emit('remove-mapping', mapping.id)"
                      class="text-gray-500 hover:text-brand ml-1 focus:outline-none">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path
                    stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </span>
          </div>
          <div v-else
               class="text-[10px] uppercase font-bold tracking-wider text-gray-600 mt-3 border border-dashed border-gray-700 inline-block px-2 py-1 rounded">
            Перетащите сырые термины сюда
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
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #4b5563;
}
</style>