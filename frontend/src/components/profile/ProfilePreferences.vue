<script setup>
import {ref, watch} from 'vue';

const props = defineProps({
  initialPrefs: {type: Object, required: true},
  csrfToken: {type: String, required: true}
});

const prefs = ref({...props.initialPrefs});
const voiceoversInput = ref((props.initialPrefs.preferred_voiceovers || []).join(', '));
const isSaving = ref(false);
const saveMessage = ref('');

watch(() => props.initialPrefs, (newVal) => {
  prefs.value = {...newVal};
  voiceoversInput.value = (newVal.preferred_voiceovers || []).join(', ');
}, {deep: true});

const updatePreferences = async () => {
  isSaving.value = true;
  saveMessage.value = '';
  prefs.value.preferred_voiceovers = voiceoversInput.value
      .split(',')
      .map(s => s.trim())
      .filter(s => s);

  try {
    const res = await fetch('/api/v1/users/preferences/', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify(prefs.value)
    });
    if (res.ok) {
      saveMessage.value = 'Настройки сохранены!';
      setTimeout(() => {
        saveMessage.value = '';
      }, 3000);
    }
  } catch (e) {
    saveMessage.value = 'Ошибка при сохранении.';
  } finally {
    isSaving.value = false;
  }
};
</script>

<template>
  <div class="bg-card p-6 rounded-xl border border-gray-800 sticky top-24">
    <h2 class="text-xl font-black tracking-tighter mb-6 uppercase text-brand">Настройки плеера</h2>

    <div class="space-y-6">
      <div>
        <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Фильтр по коду языка</label>
        <input
            v-model="prefs.language_code"
            type="text"
            placeholder="например: rus, eng, jpn"
            class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm"
        >
        <p class="text-[10px] text-gray-600 mt-1">Жесткое ограничение для аудиодорожек (например, "rus").</p>
      </div>

      <div>
        <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Приоритетные озвучки</label>
        <textarea
            v-model="voiceoversInput"
            rows="3"
            placeholder="LostFilm, HDrezka, TVShows..."
            class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm resize-none"
        ></textarea>
        <p class="text-[10px] text-gray-600 mt-1">Список студий через запятую в порядке убывания приоритета.</p>
      </div>

      <label class="flex items-center gap-3 cursor-pointer group">
        <div class="relative">
          <input type="checkbox" v-model="prefs.auto_skip_intro" class="sr-only">
          <div class="block bg-gray-800 w-10 h-6 rounded-full border border-gray-700 transition"
               :class="prefs.auto_skip_intro ? 'bg-brand border-brand' : ''"></div>
          <div class="dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform"
               :class="prefs.auto_skip_intro ? 'translate-x-4' : ''"></div>
        </div>
        <div class="text-sm font-bold text-gray-300 group-hover:text-white transition">Автопропуск заставок</div>
      </label>

      <button
          @click="updatePreferences"
          :disabled="isSaving"
          class="w-full bg-gray-800 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded border border-gray-700 transition disabled:opacity-50"
      >
        {{ isSaving ? 'Сохранение...' : 'Сохранить настройки' }}
      </button>

      <div v-if="saveMessage" class="text-xs font-bold text-green-500 text-center transition-opacity">
        {{ saveMessage }}
      </div>
    </div>
  </div>
</template>