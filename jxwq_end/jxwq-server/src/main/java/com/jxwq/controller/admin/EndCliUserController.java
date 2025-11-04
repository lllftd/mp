package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.dto.ClientUserInfoEditDto;
import com.jxwq.dto.pageQuery.EndCliUserPageQueryDTO;
import com.jxwq.entity.ClientUser;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.service.admin.EndCliUserService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * @author: jxwq
 * @date: 2024/09/02
 * @description: 后台管理前台用户接口
 */
@RestController
@RequestMapping("/admin/client")
@Slf4j
@Api(tags = "后台管理客户端用户")
public class EndCliUserController {

    @Resource
    private EndCliUserService endCliUserService;

    /**
     * 前台用户分页
     *
     * @param endCliUserPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated EndCliUserPageQueryDTO endCliUserPageQueryDTO) {

        Integer pageNum = endCliUserPageQueryDTO.getPage(); // 当前页
        Integer pageSize = endCliUserPageQueryDTO.getPageSize(); // 每页条数

        LambdaQueryWrapper<ClientUser> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        // queryWrapper.orderByDesc(ClientUser::getId); // 按照id倒序 (可选)

        Page<ClientUser> page = new Page<>(pageNum, pageSize);
        endCliUserService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<ClientUser> pageResult = new PageResult<>(
                pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据

        return AjaxResult.success(pageResult);
    }

    /**
     * 后台用户信息修改 只能修改头像和昵称 新增的时候是在用户端
     *
     * @param clientUserInfoEditDTO 推文信息
     * @return AjaxResult
     */
    @ApiOperation("更新/修改用户")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated ClientUserInfoEditDto clientUserInfoEditDTO) {

        ClientUser clientUser = new ClientUser();
        BeanUtils.copyProperties(clientUserInfoEditDTO, clientUser);
        boolean result = endCliUserService.saveOrUpdate(clientUser);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    /**
     * 用户删除
     *
     * @param id 用户id
     * @return AjaxResult
     */
    @ApiOperation("删除用户")
    @PostMapping("/delete/{id}")
    public AjaxResult delete(@PathVariable("id") Integer id) {

        boolean result = endCliUserService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }
}
