import { createSSRApp } from "vue";
import * as Pinia from "pinia";
import { createUnistorage } from "pinia-plugin-unistorage"; // pinia数据持久化
import App from "./App.vue";
import uviewPlus from 'uview-plus';

export function createApp() {
  const app = createSSRApp(App);
  const store = Pinia.createPinia();
  store.use(createUnistorage());
  app.use(uviewPlus)
  app.use(store);

  return {
    app,
    Pinia,
  };
}
