package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.constant.JwtClaimsConstant;
import com.jxwq.constant.PasswordConstant;
import com.jxwq.context.BaseContext;
import com.jxwq.dto.EmployeePageQueryDto;
import com.jxwq.dto.EndUserDetailDto;
import com.jxwq.dto.EndUserLoginDto;
import com.jxwq.entity.EndUser;
import com.jxwq.properties.JwtProperties;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.result.Result;
import com.jxwq.service.admin.EndUserService;
import com.jxwq.utils.JwtUtil;
import com.jxwq.vo.EndUserLoginVo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.util.DigestUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 后台用户管理
 */
@RestController
@RequestMapping("/admin/user")
@Slf4j
@Api(tags = "后台用户管理")
public class EndUserController {

    @Resource
    private EndUserService endUserService;

    @Resource
    private JwtProperties jwtProperties;

    /**
     * 后台管理登录
     *
     * @param endUserLoginDTO 前端传过来的登录信息
     * @return 登录结果
     */
    // @Validated和@Valid区别 @Validated
    @ApiOperation("登录")
    @PostMapping("/login")
    public Result<EndUserLoginVo> login(@RequestBody @Validated EndUserLoginDto endUserLoginDTO) {
        // log.info("后台用户登录：{}", endUserLoginDTO);

        EndUser endUser = endUserService.login(endUserLoginDTO);

        // 密码是16位小写MD5加密
        // config.headers['Authorization'] = 'Bearer ' + getToken(); // 让每个请求携带自定义token 请根据实际情况自行修改
        // 登录成功后，生成jwt令牌
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.END_USER_ID, endUser.getId()); // 后台用户id
        claims.put(JwtClaimsConstant.END_USER_NAME, endUser.getUserName()); // 后台用户名
        String token = JwtUtil.createJWT(
                jwtProperties.getAdminSecretKey(), // 秘钥
                jwtProperties.getAdminTtl(), // 过期时间
                claims);

        // 制作登录成功返回信息
        EndUserLoginVo endUserLoginVO = EndUserLoginVo.builder()
                .id(endUser.getId())
                .userName(endUser.getUserName())
                .nickName(endUser.getNickName())
                .avatar(endUser.getAvatar()) // 头像
                .token(token).expiresIn(jwtProperties.getAdminTtl()) // 令牌过期时间
                .build();

        return Result.success(endUserLoginVO);
    }

    /**
     * 后台用户退出登录
     *
     * @return 结果
     */
    @ApiOperation("退出登录")
    @PostMapping("/logout")
    public AjaxResult logout() {
        // TODO 清除令牌
        return AjaxResult.success();
    }

    /**
     * 后台用户注册 暂时没有用到
     */
    @ApiOperation("注册 - 未实现")
    @PostMapping("/register")
    public Result<EndUserDetailDto> save(@RequestBody EndUserDetailDto endUserDetailDTO) {
        log.info("新增后台用户：{}", endUserDetailDTO);

        EndUser endUser = new EndUser();

        BeanUtils.copyProperties(endUserDetailDTO, endUser);

        endUser.setPassword(DigestUtils.md5DigestAsHex(PasswordConstant.DEFAULT_PASSWORD.getBytes()));
        endUser.setUpdateUser(BaseContext.getCurrentUserInfo().getId());
        endUser.setCreateUser(BaseContext.getCurrentUserInfo().getId());
        endUser.setCreateTime(LocalDateTime.now());
        endUser.setUpdateTime(LocalDateTime.now());

        endUserService.save(endUser);

        return Result.success();
    }

    /**
     * 后台用户不分页查询 暂时没有用到
     */
    @ApiOperation("不分页查询")
    @GetMapping("/list")
    public AjaxResult list() {
        return AjaxResult.success();
    }


    /**
     * 后台用户分页查询 暂时没有用到
     */
    @ApiOperation("分页查询")
    @GetMapping("/page")
    public Result<PageResult> page(EmployeePageQueryDto employeePageQueryDTO) {
        log.info("后台用户分页查询，参数为：{}", employeePageQueryDTO);

        String name = employeePageQueryDTO.getNickName();
        Integer pageNum = employeePageQueryDTO.getPage();
        Integer pageSize = employeePageQueryDTO.getPageSize();

        // 开始分页查询
        Page<EndUser> page = new Page<>(pageNum, pageSize);

        LambdaQueryWrapper<EndUser> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.orderByDesc(EndUser::getId);
        queryWrapper.like(name != null, EndUser::getNickName, name);

        endUserService.page(page, queryWrapper);

        PageResult<EndUser> pageResult = new PageResult<>();
        pageResult.setTotal(page.getTotal());
        pageResult.setRows(page.getRecords());

        return Result.success(pageResult);
    }

    @ApiOperation("根据ID查询后台用户信息")
    @GetMapping("/{id}")
    public Result<EndUserDetailDto> queryById(@PathVariable Integer id) {
        log.info("后台用户的ID为：{}", id);

        EndUser endUser = endUserService.getById(id);
        EndUserDetailDto endUserDetailDTO = new EndUserDetailDto();
        BeanUtils.copyProperties(endUser, endUserDetailDTO);

        return Result.success(endUserDetailDTO);
    }

    @ApiOperation("更新后台用户信息")
    @PutMapping
    public Result<EndUserDetailDto> update(@RequestBody EndUserDetailDto endUserDetailDTO) {
        log.info("更新后的后台用户信息：{}", endUserDetailDTO);
        EndUser endUser = new EndUser();

        BeanUtils.copyProperties(endUserDetailDTO, endUser);

        QueryWrapper<EndUser> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("id", endUser.getId());

        boolean ret = endUserService.update(endUser, queryWrapper);

        if (ret) {
            return Result.success(endUserDetailDTO);
        } else {
            return Result.error("更新失败！");
        }
    }

    /**
     * 更改后台用户状态
     *
     * @param status  状态
     * @param endUser 后台用户
     * @return 结果
     */
    @ApiOperation("更改后台用户状态")
    @PostMapping("/status/{status}")
    public AjaxResult status(@PathVariable String status, EndUser endUser) {
        endUser.setStatus(status);
        endUserService.updateById(endUser);

        return AjaxResult.success();
    }
}
