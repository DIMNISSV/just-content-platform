import './style.css';
import {createApp} from 'vue';
import VideoPlayer from './components/VideoPlayer.vue';
import Catalog from './components/Catalog.vue';
import SyncWorkbench from './components/admin/SyncWorkbench.vue';

document.addEventListener('DOMContentLoaded', () => {
    const catalogMount = document.getElementById('vue-catalog-mount');
    if (catalogMount) {
        const app = createApp(Catalog);
        app.mount('#vue-catalog-mount');
    }
    const playerMount = document.getElementById('vue-player-mount');
    if (playerMount) {
        const app = createApp(VideoPlayer, {
            contentId: playerMount.dataset.contentId,
            contentType: playerMount.dataset.contentType,
            titleId: playerMount.dataset.titleId,
            episodeId: playerMount.dataset.episodeId,
            startProgress: playerMount.dataset.startProgress,
            lastTrackGroup: playerMount.dataset.lastTrackGroup,
            lastAudioAsset: playerMount.dataset.lastAudioAsset,
            lastQuality: playerMount.dataset.lastQuality,
            csrfToken: playerMount.dataset.csrf
        });
        app.mount('#vue-player-mount');
    }

    const workbenchMount = document.getElementById('vue-workbench-mount');
    if (workbenchMount) {
        const app = createApp(SyncWorkbench, {
            objectId: workbenchMount.dataset.objectId,
            contentType: workbenchMount.dataset.contentType,
            csrfToken: workbenchMount.dataset.csrf
        });
        app.mount('#vue-workbench-mount');
    }
});