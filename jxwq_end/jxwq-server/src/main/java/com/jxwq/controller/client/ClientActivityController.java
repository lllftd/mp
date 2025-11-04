package com.jxwq.controller.client;

import com.alibaba.fastjson2.JSONObject;
import com.jxwq.context.BaseContext;
import com.jxwq.controller.admin.ActivityController;
import com.jxwq.dto.pageQuery.ActivityPageQueryDTO;
import com.jxwq.result.AjaxResult;
import com.jxwq.service.admin.ActivityService;
import com.jxwq.service.admin.VActivityJoinService;
import com.jxwq.utils.CommonUtils;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * @author: jxwq
 * @date: 2024/08/30
 * @description: 小程序活动管理接口
 */
@RestController
@RequestMapping("/client/activity")
@Slf4j
@Api(tags = "小程序活动管理")
public class ClientActivityController {

    @Resource
    private ActivityController activityController;
    @Resource
    private ActivityService activityService;
    @Resource
    private VActivityJoinService vActivityJoinService;

    /**
     * 活动分页
     *
     * @param activityPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询活动")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated ActivityPageQueryDTO activityPageQueryDTO) {
        return activityController.page(activityPageQueryDTO);
    }

    /**
     * 参加活动
     */
    @ApiOperation("参加活动")
    @PostMapping("/join")
    public AjaxResult join(@RequestBody JSONObject jsonObject) {
        Integer clientUserId = BaseContext.getCurrentUserInfo().getId(); // 获取当前用户Id
        Integer actId = jsonObject.getInteger("actId"); // 获取活动Id
        String actTitle = jsonObject.getString("actTitle"); // 获取活动名称
        Boolean getMsg = jsonObject.getBoolean("getMsg"); // 是否接受消息

        // 判断是否已参加
        if (vActivityJoinService.isJoin(clientUserId, actId)) {
            return AjaxResult.error("您已参加该活动");
        }

        // 活动参与表写入用户Id
        vActivityJoinService.joinActivity(clientUserId, actId);

        // 根据是否接受消息写入消息表
        if (getMsg) {
            vActivityJoinService.setClientMsg(clientUserId, "参与了活动 - [" + actTitle + "]");
        }

        return AjaxResult.success();
    }

    /**
     * 查询某用户参加的活动id数组
     */
    @ApiOperation("查询某用户参加的活动id数组")
    @GetMapping("/joinActivityIds")
    public AjaxResult getJoinActivityIds() {
        List<Map<String, Object>> joinActivityIds = vActivityJoinService.getJoinActivityIdsByUserId(BaseContext.getCurrentUserInfo().getId());
        List<Integer> actIds = joinActivityIds.stream().map(map -> CommonUtils.object2Int(map.get("act_id"))).collect(Collectors.toList());
        return AjaxResult.success(actIds);
    }

    /**
     * 查询某人参加的活动 TODO分页
     */
    @ApiOperation("查询某用户参加的活动")
    @GetMapping("/joinActivity")
    public AjaxResult getJoinActivity() {
        return activityController.getJoinActivity(BaseContext.getCurrentUserInfo().getId());
    }

    /**
     * 查询某人的消息记录(目前只有活动有)
     */
    @ApiOperation("查询某人的消息记录(目前只有活动有)")
    @GetMapping("/getClientMsg")
    public AjaxResult getClientMsg() {
        return AjaxResult.success(vActivityJoinService.getClientMsg(BaseContext.getCurrentUserInfo().getId()));
    }

}
