package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;

/**
 * 推文类型表
 *
 * @TableName tweets_type
 */
@TableName(value = "tweets_type")
@Data
public class TweetsType implements Serializable {
    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
    /**
     * 主键
     */
    @TableId(type = IdType.AUTO)
    private Integer id;
    /**
     * 类型名称
     */
    private String name;
    /**
     * 父类型id 一级节点为NULL
     */
    private Integer parentId;
}