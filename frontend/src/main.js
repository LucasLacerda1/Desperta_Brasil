// Fontes e icones dentro do projeto (sem chamar o Google: o navegador do visitante nao manda o IP para fora)
import '@fontsource/roboto/400.css'
import '@fontsource/roboto/500.css'
import '@fontsource/roboto/700.css'
import '@fontsource-variable/source-serif-4/index.css'
import 'material-symbols/outlined.css'

// CSS do site: Tailwind com as cores do estudo (tokens.css e base.css entram por ele)
import './estilos/principal.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router.js'
import { aplicarTemaSalvo } from './util/tema.js'

aplicarTemaSalvo()
createApp(App).use(router).mount('#app')
