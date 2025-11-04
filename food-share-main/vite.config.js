import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import uni from "@dcloudio/vite-plugin-uni";
import AutoImport from "unplugin-auto-import/vite";
import Components from "unplugin-vue-components/vite";

// https://vitejs.dev/config/
// https://uniapp.dcloud.net.cn/collocation/vite-config.html
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd());
  const { VITE_APP_BASE_URL, VITE_APP_BASE_API } = env;

  return {
    plugins: [
      uni(),
      /* 自动导入 不用每个文件都import */
      AutoImport({
        include: [/\.[tj]sx?$/, /\.vue$/, /\.vue\?vue/],
        imports: ["vue", "uni-app", "vue-router", "pinia"],
        dts: "auto-imports.d.ts",
      }),
      Components({
        // dirs 指定组件所在位置，默认为 src/components
        // 可以让我们使用自己定义组件的时候免去 import 的麻烦
        dirs: ["src/components", "src/uni_modules"],
        // 配置需要将哪些后缀类型的文件进行自动按需引入，'vue'为默认值
        // extensions: ['vue'],
        // // 解析组件，这里以 Element Plus 为例
        // // resolvers: [],
        // // 生成components.d.ts
        dts: "components.d.ts",
        // // 遍历子目录
        // deep: true,
      }),
    ],
    css: {
      preprocessorOptions: {
        scss: {
          scss: {
            // 配置项
            quietDeps: true, // 禁用警告
            // 如果需要使用其他编译选项
            sourceMap: true,
          }
        }
      }
    },
    resolve: {
      /* 路径别名 */
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    /* 接口 */
    server: {
      host: true, // 服务器主机名，如果允许外部访问，可设置为"0.0.0.0"
      // host: '0.0.0.0',
      port: 80, // 服务器端口号
      open: true, // 是否自动打开浏览器
      https: false, // 需要开启https服务
      proxy: {
        "/api": {
          target: VITE_APP_BASE_URL + VITE_APP_BASE_API, //接口地址
          changeOrigin: true,
          secure: false, //https
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    define: {},
    // build: {
    //   // 生产环境去除log语句和debug
    //   // 在开发者工具调试的话会导致小程序控制台打印不出来
    //   minify: "terser", // 启用 terser 压缩
    //   terserOptions: {
    //     compress: {
    //       drop_console: true, // 删除所有 console
    //       drop_debugger: true,
    //     },
    //   },
    // },
  };
});
