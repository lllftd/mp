package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.jxwq.constant.MessageConstant;
import com.jxwq.dto.DictDto;
import com.jxwq.entity.SysDict;
import com.jxwq.result.AjaxResult;
import com.jxwq.service.admin.SysDictService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;

/**
 * 后台用户管理
 */
@RestController
@RequestMapping("/admin/dict")
@Slf4j
@Api(tags = "系统通用操作")
public class DictController {

    @Resource
    private SysDictService sysDictService;

    @ApiOperation("查询列表")
    @GetMapping("/list")
    public AjaxResult list() {
        LambdaQueryWrapper<SysDict> queryWrapper = new LambdaQueryWrapper<>();
        List<SysDict> list = sysDictService.list(queryWrapper);
        return AjaxResult.success(list);
    }

    /**
     * 新增/修改 有id则修改，无id则新增
     *
     * @param dictDto 前端接收的字典数据
     * @return AjaxResult
     */
    @ApiOperation("新增/修改 带id为修改，无id为新增")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated DictDto dictDto) {
        SysDict sysDict = new SysDict();
        BeanUtils.copyProperties(dictDto, sysDict);
        boolean result = sysDictService.saveOrUpdate(sysDict);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    @ApiOperation("删除")
    @PostMapping("/delete/{id}")
    public AjaxResult delete(@PathVariable Integer id) {
        if (id == 1) {
            return AjaxResult.error(MessageConstant.SYSTEM_DICT_DELETE_FAILED);
        }

        boolean result = sysDictService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

}
