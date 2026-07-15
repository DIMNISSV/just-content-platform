<template>
  <div class="flex flex-col gap-6 font-sans text-gray-200">
    <div class="flex justify-between items-center bg-card p-4 rounded-lg border border-gray-800 shadow">
      <div>
        <h3 class="text-xl font-bold text-white">Панель сопоставления</h3>
        <p class="text-xs text-gray-400 mt-1">Организуйте поступающие термины в режиме реального времени.</p>
      </div>
      <button
          @click="syncPresets"
          :disabled="isSyncing"
          class="bg-brand hover:bg-red-700 text-white font-bold py-2 px-4 rounded text-sm transition disabled:opacity-50"
      >
        {{ isSyncing ? 'Синхронизация...' : 'Синхронизировать пресеты' }}
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[75vh]">
      <!-- Left Panel: Unmapped Raw Terms -->
      <div class="col-span-1 bg-card rounded-lg border border-gray-800 flex flex-col overflow-hidden shadow">
        <div class="p-4 border-b border-gray-800 bg-gray-900 flex-shrink-0">
          <h4 class="font-bold text-white mb-3">Несопоставленные термины ({{ filteredTerms.length }})</h4>
          <input
              v-model="searchQuery"
              type="text"
              placeholder="Поиск сырых терминов..."
              class="w-full bg-black border border-gray-700 rounded p-2 text-sm text-white focus:border-brand outline-none transition"
          />
        </div>
        <div class="flex-grow overflow-y-auto p-4 space-y-2 custom-scrollbar">
          <div v-if="filteredTerms.length === 0" class="text-gray-500 text-sm text-center py-4">
            Несопоставленные термины не найдены.
          </div>
          <div
              v-for="term in filteredTerms"
              :key="term.id"
              draggable="true"
              @dragstart="onDragStart($event, term)"
              class="bg-gray-800 p-3 rounded border border-gray-700 cursor-grab active:cursor-grabbing hover:border-brand transition group"
          >
            <div class="text-sm font-semibold text-white truncate">{{ term.name }}</div>
            <div class="text-[10px] text-brand uppercase font-black tracking-widest mt-1">ИСТОЧНИК: {{
                term.source_field
              }}
            </div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Taxonomy Tree -->
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

              <!-- Mapped Terms Tags -->
              <div class="flex flex-wrap gap-2 mt-3" v-if="node.mappedTerms && node.mappedTerms.length > 0">
                <span
                    v-for="mapping in node.mappedTerms"
                    :key="mapping.id"
                    class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-800 border border-gray-600 text-xs font-semibold text-gray-300"
                >
                  {{ mapping.raw_term_name }}
                  <button @click="removeMapping(mapping.id)"
                          class="text-gray-500 hover:text-brand ml-1 focus:outline-none">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path
                        stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
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
    </div>
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue';

const props = defineProps({
  csrfToken: {
    type: String,
    required: true
  }
});

const tabs = ['GENRE', 'TAG', 'TYPE', 'CATEGORY'];
const activeTab = ref('GENRE');
const searchQuery = ref('');
const isSyncing = ref(false);
const dragOverId = ref(null);

const unmappedTerms = ref([]);
const taxonomyItems = ref([]);
const mappings = ref([]);

const filteredTerms = computed(() => {
  if (!searchQuery.value) return unmappedTerms.value;
  const lower = searchQuery.value.toLowerCase();
  return unmappedTerms.value.filter(t =>
      t.name.toLowerCase().includes(lower) ||
      t.source_field.toLowerCase().includes(lower)
  );
});

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
  const typeItems = taxonomyItems.value.filter(i => i.type === activeTab.value);
  const map = {};
  const roots = [];

  typeItems.forEach(i => {
    map[i.id] = {...i, children: [], mappedTerms: []};
  });

  mappings.value.forEach(m => {
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

async function fetchAll() {
  try {
    const [termsRes, itemsRes, mappingsRes] = await Promise.all([
      fetch('/api/v1/taxonomy/raw-terms/?mapped=false'),
      fetch('/api/v1/taxonomy/items/'),
      fetch('/api/v1/taxonomy/mappings/')
    ]);
    unmappedTerms.value = await termsRes.json();
    taxonomyItems.value = await itemsRes.json();
    mappings.value = await mappingsRes.json();
  } catch (error) {
    console.error("Error fetching taxonomy data:", error);
  }
}

function onDragStart(e, term) {
  e.dataTransfer.setData('termId', term.id);
  e.dataTransfer.effectAllowed = 'move';
}

async function onDrop(e, taxItem) {
  dragOverId.value = null;
  const termId = e.dataTransfer.getData('termId');
  if (!termId) return;

  try {
    const res = await fetch('/api/v1/taxonomy/mappings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({
        raw_term: termId,
        taxonomy_item: taxItem.id
      })
    });
    if (res.ok) {
      await fetchAll();
    } else {
      console.error("Failed to map term", await res.json());
    }
  } catch (error) {
    console.error("Network error during drop mapping", error);
  }
}

async function removeMapping(mappingId) {
  try {
    const res = await fetch(`/api/v1/taxonomy/mappings/${mappingId}/`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': props.csrfToken
      }
    });
    if (res.ok) {
      await fetchAll();
    }
  } catch (error) {
    console.error("Error removing mapping:", error);
  }
}

async function syncPresets() {
  isSyncing.value = true;
  try {
    const res = await fetch('/api/v1/taxonomy/sync-presets/', {
      method: 'POST',
      headers: {'X-CSRFToken': props.csrfToken}
    });
    if (res.ok) {
      await fetchAll();
    } else {
      const data = await res.json();
      alert('Ошибка при синхронизации пресетов: ' + data.message);
    }
  } catch (error) {
    console.error("Sync preset error:", error);
  } finally {
    isSyncing.value = false;
  }
}

onMounted(() => {
  fetchAll();
});
</script>

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