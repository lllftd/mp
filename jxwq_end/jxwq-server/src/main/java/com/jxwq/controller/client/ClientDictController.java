package com.jxwq.controller.client;

import com.jxwq.entity.SysDict;
import com.jxwq.result.AjaxResult;
import com.jxwq.service.admin.SysDictService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.log4j.Log4j2;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;

@RestController
@Log4j2
@Api(tags = "客户端用户管理")
@RequestMapping("/client/dict")
public class ClientDictController {

    @Resource
    private SysDictService sysDictService;

    @ApiOperation("获取兴趣标签字典")
    @GetMapping("/tag")
    public AjaxResult getTag() {
        SysDict sysDict = sysDictService.getById("1");
        if (sysDict != null) {
            return AjaxResult.success("操作成功", sysDict.getDictValue());
        }
        return AjaxResult.error("兴趣标签获取失败");
    }
}
