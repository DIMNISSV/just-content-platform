<template>
  <div class="border-l border-gray-700 pl-4 ml-2 mt-3 relative">
    <div v-if="isLogical" class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="node.type"
              class="bg-gray-800 border border-gray-700 text-white text-xs px-3 py-1.5 rounded outline-none focus:border-brand transition">
        <option value="AND">AND</option>
        <option value="OR">OR</option>
        <option value="NOT">NOT</option>
      </select>
      <button @click="addRule"
              class="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded transition">
        + Rule
      </button>
      <button @click="addGroup"
              class="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded transition">
        + Group
      </button>
      <button v-if="isRemovable" @click="$emit('remove')"
              class="text-xs text-brand hover:text-red-400 px-3 py-1.5 transition">
        Remove
      </button>
    </div>

    <div v-else class="flex flex-wrap items-center gap-2 mb-2 bg-gray-900 p-2 rounded border border-gray-800">
      <select v-model="node.field" @change="onFieldChange"
              class="bg-gray-800 border border-gray-700 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-brand">
        <option value="genre">Genre</option>
        <option value="tag">Tag</option>
        <option value="category">Category</option>
        <option value="type">Type</option>
        <option value="release_year">Release Year</option>
        <option value="rating_score">Rating Score</option>
        <option value="name">Title Name</option>
      </select>

      <select v-model="node.operator"
              class="bg-gray-800 border border-gray-700 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-brand">
        <option value="exact">Equals</option>
        <option value="icontains" v-if="node.field === 'name'">Contains</option>
        <option value="gt" v-if="!['genre', 'tag', 'category', 'type', 'name'].includes(node.field)">Greater Than
        </option>
        <option value="lt" v-if="!['genre', 'tag', 'category', 'type', 'name'].includes(node.field)">Less Than</option>
      </select>

      <input v-if="!['genre', 'tag', 'category', 'type'].includes(node.field)" type="text" v-model="node.value"
             class="bg-gray-800 border border-gray-700 text-white text-xs px-3 py-1.5 rounded outline-none focus:border-brand"
             placeholder="Value">

      <select v-if="node.field === 'type'" v-model="node.value"
              class="bg-gray-800 border border-gray-700 text-white text-xs px-3 py-1.5 rounded outline-none focus:border-brand">
        <option value="MOVIE">Movie</option>
        <option value="SERIES">Series</option>
      </select>

      <select v-if="['genre', 'tag', 'category'].includes(node.field)" v-model="node.value"
              class="bg-gray-800 border border-gray-700 text-white text-xs px-3 py-1.5 rounded outline-none focus:border-brand">
        <option v-for="t in filteredTaxonomy" :key="t.slug" :value="t.slug">{{ t.name }}</option>
      </select>

      <button @click="$emit('remove')" class="text-xs text-brand hover:text-red-400 px-2 transition ml-auto">
        Remove
      </button>
    </div>

    <div v-if="isLogical && node.children && node.children.length > 0" class="flex flex-col gap-1">
      <SearchNode
          v-for="(child, index) in node.children"
          :key="index"
          :node="child"
          :isRemovable="true"
          :taxonomyItems="taxonomyItems"
          @remove="removeChild(index)"
      />
    </div>
  </div>
</template>

<script setup>
import {computed} from 'vue';

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  isRemovable: {
    type: Boolean,
    default: false
  },
  taxonomyItems: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['remove']);

const isLogical = computed(() => ['AND', 'OR', 'NOT'].includes(props.node.type));

const filteredTaxonomy = computed(() => {
  if (props.node.field === 'genre') return props.taxonomyItems.filter(i => i.type === 'GENRE');
  if (props.node.field === 'tag') return props.taxonomyItems.filter(i => i.type === 'TAG');
  if (props.node.field === 'category') return props.taxonomyItems.filter(i => i.type === 'CATEGORY');
  return [];
});

const onFieldChange = () => {
  props.node.value = '';
};

const addRule = () => {
  if (!props.node.children) props.node.children = [];
  props.node.children.push({
    type: 'RULE',
    field: 'genre',
    operator: 'exact',
    value: ''
  });
};

const addGroup = () => {
  if (!props.node.children) props.node.children = [];
  props.node.children.push({
    type: 'AND',
    children: []
  });
};

const removeChild = (index) => {
  props.node.children.splice(index, 1);
};
</script>