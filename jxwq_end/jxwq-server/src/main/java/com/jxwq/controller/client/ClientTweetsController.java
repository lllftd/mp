package com.jxwq.controller.client;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.context.BaseContext;
import com.jxwq.controller.admin.TweetsController;
import com.jxwq.dto.TweetDto;
import com.jxwq.dto.pageQuery.TweetsPageQueryDTO;
import com.jxwq.entity.Tweets;
import com.jxwq.entity.VTweets;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.service.admin.TweetsService;
import com.jxwq.service.admin.TweetsTypeService;
import com.jxwq.service.admin.VTweetsService;
import com.jxwq.service.client.RandTweetService;
import com.jxwq.utils.CommonUtils;
import com.jxwq.utils.StringUtils;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * @author: jxwq
 * @date: 2024/08/30
 * @description: 推文管理接口
 */
@RestController
@RequestMapping("/client/tweets")
@Slf4j
@Api(tags = "客户端推文管理")
public class ClientTweetsController {

    @Resource
    private TweetsController tweetsController;
    @Resource
    private TweetsService tweetsService;
    @Resource
    private VTweetsService vTweetsService;
    @Resource
    private RandTweetService randTweetService;
    @Resource
    private TweetsTypeService tweetsTypeService;
    @Resource
    private ClientUserController clientUserController;
    @Resource
    private com.jxwq.service.client.RecommendationService recommendationService;
    @Resource
    private com.jxwq.service.client.RecommendationFeedbackService recommendationFeedbackService;

    /**
     * 随机获取十条推文
     */
    @ApiOperation("随机获取十条推文")
    @PostMapping("/rand")
    public AjaxResult randTweets(@RequestBody JSONObject jsonObject) {
        Integer clientUserId = null;
        try {
            clientUserId = jsonObject.getInteger("clientUserId"); // 获取当前用户Id
        } catch (Exception e) {
            log.error("未登录不需要获取当前用户Id");
        }

        String searchTypeKeyword = jsonObject.getString("searchTypeKeyword"); // 搜索类型关键字
        List<Map<String, Object>> list = randTweetService.recommendTweets(clientUserId, searchTypeKeyword);
        return AjaxResult.success(list);
    }

    /**
     * 获取推文 通过点赞量或发布时间
     * 推文获取的排序类型 hot点赞量 new发布时间
     */
    @ApiOperation("获取推文-通过点赞量或发布时间")
    @GetMapping("/pageQuery")
    public AjaxResult pageQuery(@RequestParam Map<String, String> params) {

        // 将 Map 转换为 JSONObject
        JSONObject jsonObject = JSON.parseObject(JSON.toJSONString(params));
        Integer pageNum = jsonObject.getInteger("page"); // 当前页
        Integer pageSize = jsonObject.getInteger("pageSize"); // 每页条数
        String tweetsOrderBy = jsonObject.getString("type"); // 推文获取的排序类型

        LambdaQueryWrapper<VTweets> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        queryWrapper.orderByDesc(Objects.equals("Hot", tweetsOrderBy), VTweets::getLikeNum); // 点赞量正序
        queryWrapper.orderByDesc(Objects.equals("New", tweetsOrderBy), VTweets::getCreateTime); // 发布时间正序

        Page<VTweets> page = new Page<>(pageNum, pageSize);
        vTweetsService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<VTweets> pageResult = new PageResult<>(pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据
        return AjaxResult.success(pageResult);
    }

    /**
     * 获取推文详情
     */
    @ApiOperation("获取详情")
    @GetMapping("/detail/{id}")
    public AjaxResult tweetsDetail(@PathVariable("id") Integer id) {
        VTweets vTweets = vTweetsService.getOne(new LambdaQueryWrapper<VTweets>().eq(VTweets::getId, id));
        return AjaxResult.success(vTweets);
    }

    /**
     * 写入推文点赞收藏记录 可以取消
     */
    @ApiOperation("推文点赞收藏")
    @PostMapping("/tweetsLikeCollect")
    public AjaxResult tweetsCollect(@RequestBody JSONObject jsonObject) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        Integer tweetsId = jsonObject.getInteger("tweetsId"); // 推文Id
        Integer tweetsRecordId = jsonObject.getInteger("tweetsRecordId"); // 推文记录Id
        String type = jsonObject.getString("type"); // 类型：like 点赞 collect 收藏
        String flag = jsonObject.getString("flag"); // 新增或者删除
        if ("add".equals(flag)) {
            // 如果是新增点赞，查询是否点赞，是的话修改记录
            if ("like".equals(type)) {
                List<Map<String, Object>> list = tweetsService.getLikeRecord(clientUserId, tweetsId);
                if (!list.isEmpty()) {
                    tweetsService.updateTweetsRecordCreateTime(clientUserId, CommonUtils.object2Int(list.get(0).get("id")));
                    return AjaxResult.success();
                }
            }

            tweetsService.insertTweetsRecord(clientUserId, tweetsId, type);
        } else {
            tweetsService.deleteTweetsRecord(tweetsRecordId);
        }

        // 推文表点赞/收藏＋-1
        Map<String, Object> map = new HashMap<>();
        map.put("id", tweetsId);
        map.put("type", type);
        map.put("add".equals(flag) ? "add" : "sub", true);
        tweetsService.updateTweetsCount(map);

        return AjaxResult.success();
    }

    /**
     * 写入推文浏览 不可取消
     */
    @ApiOperation("推文浏览")
    @PostMapping("/tweetsBrowse/{tweetsId}")
    public AjaxResult tweetsBrowse(@PathVariable Integer tweetsId) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        // 先查询有没有浏览过 如果没有浏览过，则增加一条浏览记录 如果有浏览过，修改浏览记录的创建时间
        List<Map<String, Object>> browseRecord = tweetsService.getBrowseRecord(clientUserId, tweetsId);
        if (browseRecord.isEmpty()) {
            tweetsService.insertTweetsRecord(clientUserId, tweetsId, "browse");
        } else {
            tweetsService.updateTweetsRecordCreateTime(clientUserId, CommonUtils.object2Int(browseRecord.get(0).get("id")));
        }
        // 推文表浏览数＋1
        Map<String, Object> map = new HashMap<>();
        map.put("id", tweetsId);
        map.put("type", "browse");
        map.put("add", true);
        tweetsService.updateTweetsCount(map);

        return AjaxResult.success();
    }

    /**
     * 查询当前推文是否点赞收藏
     */
    @ApiOperation("查询当前推文是否点赞收藏")
    @GetMapping("/tweetsIsLikeCollect/{tweetsId}")
    public AjaxResult tweetsIsLikeCollect(@PathVariable Integer tweetsId) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        List<Map<String, Object>> list = tweetsService.getIsLikeCollect(clientUserId, tweetsId);

        Map<String, Object> map = new HashMap<>();
        map.put("like", false);
        map.put("collect", false);

        // 如果没有点赞或收藏，则返回空
        if (list.isEmpty()) {
            return AjaxResult.success(map);
        } else {
            // 如果有点赞或收藏，则返回对应的类型
            list.forEach(item -> {
                if ("like".equals(item.get("type"))) {
                    map.put("like", true);
                    map.put("likeRecordId", item.get("id"));
                } else if ("collect".equals(item.get("type"))) {
                    map.put("collect", true);
                    map.put("collectRecordId", item.get("id"));
                }
            });
        }


        return AjaxResult.success(map);
    }

    /**
     * 推文点赞收藏浏览查询 带分页
     * 类型：like 点赞 collect 收藏 browse 浏览
     */
    @ApiOperation("推文点赞收藏浏览查询")
    @PostMapping("/tweetsRecord")
    public AjaxResult tweetsRecord(@RequestBody JSONObject jsonObject) {
        if (StringUtils.isBlank(jsonObject.getString("type"))) {
            return AjaxResult.error("未选择类型");
        }

        Integer userId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        String type = jsonObject.getString("type");
        Integer page = jsonObject.getInteger("page"); // 当前页
        Integer pageSize = jsonObject.getInteger("pageSize"); // 一页显示多少条

        Integer tweetsRecordsTotal = tweetsService.countTweetsRecords(type, userId);

        // #{pageSize,jdbcType=INTEGER}：每页显示的记录数。
        // #{offset,jdbcType=INTEGER}：起始位置，计算公式为 (currentPage - 1) * pageSize，其中 currentPage 是当前页码。

        List<Map<String, Object>> rows = tweetsService.getRecordListByTypeAndUserId(
                userId, type,
                pageSize, (page - 1) * pageSize);

        Map<String, Object> data = new HashMap<>();
        data.put("page", page);
        data.put("pageSize", pageSize);
        data.put("total", tweetsRecordsTotal);
        data.put("totalPage", tweetsRecordsTotal / pageSize + (tweetsRecordsTotal % pageSize > 0 ? 1 : 0));
        data.put("rows", rows);

        return AjaxResult.success(data);
    }

    /**
     * 推文分页
     *
     * @param tweetsPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询推文")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated TweetsPageQueryDTO tweetsPageQueryDTO) {
        Integer pageNum = tweetsPageQueryDTO.getPage(); // 当前页
        Integer pageSize = tweetsPageQueryDTO.getPageSize(); // 每页条数
        Integer tweetsTypePid = tweetsPageQueryDTO.getTweetsTypePid(); // 推文类型 一级类目

        LambdaQueryWrapper<VTweets> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        // queryWrapper.orderByDesc(Tweets::getId); // 按照id倒序 (可选)
        queryWrapper.eq(Objects.nonNull(tweetsTypePid), VTweets::getTweetsTypePid, tweetsTypePid);

        Page<VTweets> page = new Page<>(pageNum, pageSize);
        vTweetsService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<VTweets> pageResult = new PageResult<>(pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据

        return AjaxResult.success(pageResult);
    }

    /**
     * 推文新增修改
     *
     * @param tweetDto 推文信息
     * @return AjaxResult
     */
    @ApiOperation("新增/修改推文")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated TweetDto tweetDto) {
        Tweets tweets = new Tweets();
        BeanUtils.copyProperties(tweetDto, tweets);
        boolean result = tweetsService.saveOrUpdate(tweets);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    @ApiOperation("获取推文类型列表")
    @GetMapping("/tweetsType")
    public AjaxResult getTweetsTypeDict() {
        return tweetsController.getTweetsTypeDict();
    }

    @ApiOperation("发布推文评论")
    @PostMapping("/tweetsEvaluate")
    public AjaxResult sendTweetsEvaluate(@RequestBody JSONObject jsonObject) throws IOException {
        Integer userId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        Integer tweetsId = jsonObject.getInteger("tweetsId"); // 推文Id
        String evaluateContent = jsonObject.getString("evaluateContent"); // 评论内容
        String evaluateImg = jsonObject.getString("evaluateImg"); // 评论图片
        String openId = jsonObject.getString("openId"); // 微信用户openId

        if (StringUtils.isBlank(evaluateContent)) {
            return AjaxResult.error("评论内容不能为空");
        }

        // 做兼容 传了openid 则进行微信昵称违规检测
        if (!StringUtils.isBlank(openId)) {
            JSONObject wxMsgSecCheckResult = clientUserController.wxMsgSecCheck(evaluateContent, openId); // 微信内容安全检测
            if ("risky".equals(wxMsgSecCheckResult.getString("suggest"))) {
                return AjaxResult.error("评论内容违规，请检查");
            }
        }


        Map<String, Object> map = new HashMap<>();
        map.put("clientUserId", userId);
        map.put("tweetsId", tweetsId);
        map.put("evaluateContent", evaluateContent);
        map.put("evaluateImg", evaluateImg);
        tweetsService.insertTweetsEvaluate(map);

        return AjaxResult.success();
    }

    @ApiOperation("获取推文评论列表")
    @GetMapping("/tweetsEvaluateList/{tweetsId}")
    public AjaxResult sendTweetsEvaluate(@PathVariable Integer tweetsId) {
        List<Map<String, Object>> list = tweetsService.getTweetsEvaluate(tweetsId);
        return AjaxResult.success(list);
    }

    /**
     * 获取推荐推文（传统推荐算法：协同过滤+内容过滤）
     *
     * @param jsonObject 请求参数
     * @return AjaxResult
     */
    @ApiOperation("获取推荐推文（混合推荐：协同过滤+内容过滤）")
    @PostMapping("/recommendations")
    public AjaxResult getRecommendations(@RequestBody JSONObject jsonObject) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        Integer topN = jsonObject.getInteger("topN"); // 推荐数量
        
        // 使用配置的推荐方法（默认hybrid：混合推荐）
        List<Integer> recommendationIds = recommendationService.getRecommendations(clientUserId, null, topN);

        // 根据推荐ID获取推文详情
        if (recommendationIds.isEmpty()) {
            return AjaxResult.success(new ArrayList<>());
        }

        LambdaQueryWrapper<VTweets> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(VTweets::getId, recommendationIds);
        // 保持推荐顺序
        queryWrapper.last("ORDER BY FIELD(id, " + String.join(",", recommendationIds.stream().map(String::valueOf).toArray(String[]::new)) + ")");
        List<VTweets> recommendedTweets = vTweetsService.list(queryWrapper);

        return AjaxResult.success(recommendedTweets);
    }

    /**
     * 提交推荐反馈（强化学习：左滑/右滑）
     */
    @ApiOperation("提交推荐反馈")
    @PostMapping("/recommendations/feedback")
    public AjaxResult submitRecommendationFeedback(@RequestBody JSONObject jsonObject) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId();
        Integer tweetsId = jsonObject.getInteger("tweetsId");
        String feedback = jsonObject.getString("feedback"); // like / dislike

        if (tweetsId == null || StringUtils.isBlank(feedback)) {
            return AjaxResult.error("参数错误");
        }

        recommendationFeedbackService.saveFeedback(clientUserId, tweetsId, feedback);
        return AjaxResult.success();
    }

    /**
     * 获取热门推文
     *
     * @param jsonObject 请求参数
     * @return AjaxResult
     */
    @ApiOperation("获取热门推文")
    @PostMapping("/popular")
    public AjaxResult getPopularTweets(@RequestBody JSONObject jsonObject) {
        Integer topN = jsonObject.getInteger("topN"); // 推荐数量，默认20

        List<Integer> popularIds = recommendationService.getPopularItems(topN);

        if (popularIds.isEmpty()) {
            return AjaxResult.success(new ArrayList<>());
        }

        LambdaQueryWrapper<VTweets> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.in(VTweets::getId, popularIds);
        queryWrapper.orderByDesc(VTweets::getLikeNum);
        List<VTweets> popularTweets = vTweetsService.list(queryWrapper);

        return AjaxResult.success(popularTweets);
    }

}
