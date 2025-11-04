package com.jxwq.service.client;

import com.alibaba.fastjson2.JSONObject;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 推荐服务
 * 调用Python推荐算法脚本
 *
 * @author system
 */
@Slf4j
@Service
public class RecommendationService {

    /**
     * Python脚本路径，从配置文件读取
     */
    @Value("${recommendation.python.path:/path/to/recommendation-service}")
    private String pythonScriptPath;

    /**
     * Python命令（python3 或 python）
     */
    @Value("${recommendation.python.command:python3}")
    private String pythonCommand;

    /**
     * 推荐方法：hybrid（混合推荐，协同过滤+内容过滤）
     * 支持的方法：collaborative/cf, content/cb, hybrid, popular
     */
    @Value("${recommendation.service.method:hybrid}")
    private String recommendationMethod;

    /**
     * 默认推荐数量
     */
    @Value("${recommendation.service.count:20}")
    private Integer recommendationCount;

    /**
     * 执行Python脚本并获取结果
     *
     * @param scriptName 脚本名称（如 get_recommendations.py）
     * @param args       脚本参数
     * @return JSONObject格式的结果
     */
    private JSONObject executePythonScript(String scriptName, String... args) {
        Process process = null;
        BufferedReader reader = null;
        BufferedReader errorReader = null;
        
        try {
            // 构建命令
            List<String> command = new ArrayList<>();
            command.add(pythonCommand);
            command.add(pythonScriptPath + "/" + scriptName);
            
            if (args != null) {
                for (String arg : args) {
                    command.add(arg);
                }
            }
            
            log.debug("执行Python命令: {}", String.join(" ", command));
            
            // 执行Python脚本
            ProcessBuilder pb = new ProcessBuilder(command);
            pb.redirectErrorStream(false); // 错误输出单独处理
            process = pb.start();
            
            // 读取标准输出
            reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8)
            );
            
            // 读取错误输出
            errorReader = new BufferedReader(
                new InputStreamReader(process.getErrorStream(), StandardCharsets.UTF_8)
            );
            
            // 读取输出内容
            StringBuilder output = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
            
            // 读取错误内容
            StringBuilder errorOutput = new StringBuilder();
            String errorLine;
            while ((errorLine = errorReader.readLine()) != null) {
                errorOutput.append(errorLine).append("\n");
            }
            
            // 等待进程完成
            int exitCode = process.waitFor();
            
            if (exitCode != 0) {
                log.error("Python脚本执行失败，退出码: {}, 错误信息: {}", exitCode, errorOutput.toString());
                return null;
            }
            
            if (errorOutput.length() > 0) {
                log.warn("Python脚本警告: {}", errorOutput.toString());
            }
            
            // 解析JSON结果
            String resultString = output.toString();
            if (resultString == null || resultString.trim().isEmpty()) {
                log.error("Python脚本返回空结果");
                return null;
            }
            
            return JSONObject.parseObject(resultString);
            
        } catch (Exception e) {
            log.error("执行Python脚本异常: {}", e.getMessage(), e);
            return null;
        } finally {
            // 关闭资源
            try {
                if (reader != null) {
                    reader.close();
                }
                if (errorReader != null) {
                    errorReader.close();
                }
                if (process != null) {
                    process.destroy();
                }
            } catch (Exception e) {
                log.error("关闭进程资源异常: {}", e.getMessage(), e);
            }
        }
    }

    /**
     * 获取用户推荐（使用传统推荐算法）
     *
     * @param userId 用户ID
     * @param method 推荐方法（collaborative/cf, content/cb, hybrid, popular）
     * @param topN   推荐数量（可选，默认使用配置的数量）
     * @return 推荐推文ID列表
     */
    public List<Integer> getRecommendations(Integer userId, String method, Integer topN) {
        try {
            // 准备参数（使用配置的方法或传入的方法）
            String finalMethod = (method != null && !method.isEmpty()) ? method : recommendationMethod;
            // 如果传入的是无效方法，使用默认的hybrid
            if (!finalMethod.matches("collaborative|cf|content|cb|hybrid|popular")) {
                finalMethod = "hybrid";
            }
            Integer finalTopN = (topN != null && topN > 0) ? topN : recommendationCount;
            
            // 执行Python脚本
            JSONObject jsonResponse = executePythonScript(
                "get_recommendations.py",
                String.valueOf(userId),
                finalMethod,
                String.valueOf(finalTopN)
            );
            
            if (jsonResponse != null && jsonResponse.getInteger("code") == 200) {
                List<Integer> recommendations = new ArrayList<>();
                List<Object> data = jsonResponse.getList("data", Object.class);
                if (data != null) {
                    for (Object item : data) {
                        if (item instanceof Number) {
                            recommendations.add(((Number) item).intValue());
                        }
                    }
                }
                log.info("获取用户 {} 推荐成功，推荐数量: {}", userId, recommendations.size());
                return recommendations;
            } else {
                String message = jsonResponse != null ? jsonResponse.getString("message") : "Unknown error";
                log.warn("获取推荐失败: {}", message);
                // 失败时返回热门物品
                return getPopularItems(finalTopN);
            }
            
        } catch (Exception e) {
            log.error("获取推荐异常: {}", e.getMessage(), e);
            // 异常时返回热门物品
            return getPopularItems(topN != null ? topN : recommendationCount);
        }
    }

    /**
     * 获取热门物品
     *
     * @param topN 推荐数量
     * @return 热门推文ID列表
     */
    public List<Integer> getPopularItems(Integer topN) {
        try {
            Integer finalTopN = (topN != null && topN > 0) ? topN : recommendationCount;
            
            // 执行Python脚本
            JSONObject jsonResponse = executePythonScript(
                "get_popular.py",
                String.valueOf(finalTopN)
            );
            
            if (jsonResponse != null && jsonResponse.getInteger("code") == 200) {
                List<Integer> popularItems = new ArrayList<>();
                List<Object> data = jsonResponse.getList("data", Object.class);
                if (data != null) {
                    for (Object item : data) {
                        if (item instanceof Number) {
                            popularItems.add(((Number) item).intValue());
                        }
                    }
                }
                log.info("获取热门物品成功，数量: {}", popularItems.size());
                return popularItems;
            }
            
        } catch (Exception e) {
            log.error("获取热门物品异常: {}", e.getMessage(), e);
        }
        
        return new ArrayList<>();
    }

    /**
     * 批量获取推荐
     * 批量推荐是循环调用单个推荐方法
     *
     * @param userIds 用户ID列表
     * @param method  推荐方法
     * @param topN    推荐数量
     * @return 用户ID -> 推荐列表的映射
     */
    public Map<Integer, List<Integer>> getBatchRecommendations(List<Integer> userIds, String method, Integer topN) {
        Map<Integer, List<Integer>> results = new HashMap<>();
        
        try {
            // 循环调用单个推荐方法
            for (Integer userId : userIds) {
                List<Integer> recommendations = getRecommendations(userId, method, topN);
                results.put(userId, recommendations);
            }
            
            log.info("批量获取推荐成功，用户数量: {}", results.size());
            
        } catch (Exception e) {
            log.error("批量获取推荐异常: {}", e.getMessage(), e);
            // 为每个用户返回热门物品
            List<Integer> popularItems = getPopularItems(topN != null ? topN : recommendationCount);
            for (Integer userId : userIds) {
                results.put(userId, new ArrayList<>(popularItems));
            }
        }
        
        return results;
    }
}

