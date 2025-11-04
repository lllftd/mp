package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 客户端用户表
 *
 * @TableName client_user
 */
@TableName(value = "client_user")
@Data
public class ClientUser implements Serializable {
    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
    /**
     * 主键
     */
    @TableId(type = IdType.AUTO)
    private Integer id;
    /**
     * 微信唯一标识
     */
    private String openId;
    /**
     * 用户昵称
     */
    private String nickName;
    /**
     * 用户头像
     */
    private String avatar;
    /**
     * 手机号
     */
    private String phone;
    /**
     * 性别 0女 1男
     */
    private String sex;
    /**
     * 地区
     */
    private String location;
    /**
     * 标签
     */
    private String tags;
    /**
     * 状态 0禁用，1启用
     */
    private String status;
    /**
     * 是否接收消息推送 是否接收消息推送 - 0不接收 1接收
     */
    private String getMsg;
    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime createTime;
    /**
     * 修改时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime updateTime;
    /**
     * 创建人
     */
    // 这时候还没有创建用户，所以暂时不用填
    // @TableField(fill = FieldFill.INSERT)
    private String createUser;
    /**
     * 修改人
     */
    // @TableField(fill = FieldFill.INSERT_UPDATE)
    private String updateUser;
}