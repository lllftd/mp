package com.jxwq.dto;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import org.hibernate.validator.constraints.Length;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.io.Serializable;

@Data
public class TweetDto implements Serializable {

    private static final long serialVersionUID = 1L;

    private Integer id; // 主键

    /**
     * 推文类型 一级类目
     */
    @NotNull(message = "推文一级类目不能为空")
    @ApiModelProperty("推文一级类目")
    private Integer tweetsTypePid;

    /**
     * 推文类型 二级类目
     */
    @NotEmpty(message = "推文二级类目不能为空")
    @ApiModelProperty("推文二级类目")
    private String tweetsTypeCid;

    /**
     * 推文标题
     */
    @NotEmpty(message = "推文标题不能为空")
    @Length(max = 15, message = "推文标题长度不能超过 15 位")
    @ApiModelProperty("推文标题")
    private String tweetsTitle;

    /**
     * 推文作者
     */
    private String tweetsUser;

    /**
     * 推文简介
     */
    @NotEmpty(message = "推文简介不能为空")
    @Length(max = 300, message = "推文简介长度不能超过 300 字")
    @ApiModelProperty("推文简介")
    private String tweetsDescribe;

    /**
     * 推文图片
     */
    @NotEmpty(message = "推文图片不能为空")
    @Length(min = 4, message = "推文图片不能为空") // "[图片1,图片2,图片3,图片4]"
    @ApiModelProperty("推文图片")
    private String tweetsImg;

    /**
     * 推文内容
     */
    @NotEmpty(message = "推文内容不能为空")
    @ApiModelProperty("推文内容")
    private String tweetsContent;

    private Integer browseNum; // 浏览数
    private Integer likeNum; // 点赞数
    private Integer collectNum; // 收藏数

}