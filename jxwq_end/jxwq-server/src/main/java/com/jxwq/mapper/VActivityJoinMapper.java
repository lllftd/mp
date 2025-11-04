package com.jxwq.mapper;


import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.jxwq.entity.VActivityJoin;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【v_activity_join】的数据库操作Mapper
 * @createDate 2024-09-09 00:31:06
 * @Entity generator.domain.VActivityJoin
 */
public interface VActivityJoinMapper extends BaseMapper<VActivityJoin> {

    List<Map<String, Object>> getJoinActivityIdsByUserId(@Param("clientUserId") Integer clientUserId);

    Integer isJoin(@Param("clientUserId") Integer clientUserId, @Param("actId") Integer actId);

    void joinActivity(@Param("clientUserId") Integer clientUserId, @Param("actId") Integer actId);

    void setClientMsg(@Param("clientUserId") Integer clientUserId, @Param("msgContent") String msgContent);

    List<Map<String, Object>> getClientMsg(@Param("clientUserId") Integer clientUserId);

}




