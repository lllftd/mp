import { defineStore } from "pinia";

export const useUserStore = defineStore("user", {
  state: () => ({
    userInfo: {},
  }),
  getters: {},
  actions: {
    setUserInfo(data) {
      this.userInfo = data;
    },
  },
});
