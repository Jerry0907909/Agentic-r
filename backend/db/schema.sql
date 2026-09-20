-- ============================================================================
-- Agentic RAG 医疗智能问答系统 · 数据库 DDL
-- ----------------------------------------------------------------------------
-- 对应文档：系统设计.md §3.2 建表 DDL
-- 目标库  ：MySQL 9.x，字符集 utf8mb4 / 排序规则 utf8mb4_0900_ai_ci
--
-- 用法（二选一）：
--   1) 自动建库建表（推荐，幂等，可反复执行）
--        cd backend && python db/init_db.py
--   2) 手动执行本文件
--        mysql -h127.0.0.1 -uroot -p < backend/db/schema.sql
--
-- 本文件与 db/models.py 的 ORM 定义必须保持一致；改表结构时两边同步改。
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `agentic_rag`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `agentic_rag`;

-- ----------------------------------------------------------------------------
-- conversation：会话表
--   主键用 UUID（CHAR(36)）而不是自增：会话 ID 会暴露给前端（URL / localStorage /
--   请求参数），UUID 不可枚举、不泄露创建顺序与总量。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `conversation` (
  `id`            CHAR(36)     NOT NULL                COMMENT '会话ID（UUID v4）',
  `title`         VARCHAR(120) NOT NULL DEFAULT '新会话' COMMENT '会话标题，默认取首条提问前 20 字',
  `agent_type`    VARCHAR(20)  NOT NULL DEFAULT 'rag'   COMMENT '所属智能体：rag | graph',
  `message_count` INT UNSIGNED NOT NULL DEFAULT 0       COMMENT '消息条数（冗余计数，列表页免 COUNT）',
  `total_tokens`  INT UNSIGNED NOT NULL DEFAULT 0       COMMENT '累计 token（冗余，便于成本核算）',
  `created_at`    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  -- 会话列表固定按「最近更新」倒序，降序索引可完全避免 filesort
  KEY `idx_updated_at` (`updated_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话表';

-- ----------------------------------------------------------------------------
-- message：消息表
--   主键用自增 BIGINT（而非 UUID）：消息 ID 仅服务端内部使用，自增在 InnoDB
--   聚簇索引下写入有序、无页分裂，性能优于随机 UUID。
--   sources 存 JSON 列而非独立表：溯源永远整体读写，从不单独查询某条来源
--   （见 系统设计.md ADR-2）。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `message` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键（写入有序）',
  `conversation_id`   CHAR(36)        NOT NULL  COMMENT '所属会话',
  `role`              VARCHAR(10)     NOT NULL  COMMENT 'user | assistant',
  `content`           MEDIUMTEXT      NOT NULL  COMMENT '消息正文（Markdown）',
  `sources`           JSON            NULL      COMMENT '溯源来源数组，结构见系统设计 §1.6',
  `prompt_tokens`     INT UNSIGNED    NULL      COMMENT '输入 token（仅 assistant 有值）',
  `completion_tokens` INT UNSIGNED    NULL      COMMENT '输出 token',
  `total_tokens`      INT UNSIGNED    NULL      COMMENT '总 token',
  `model`             VARCHAR(64)     NULL      COMMENT '实际调用的模型名',
  `latency_ms`        INT UNSIGNED    NULL      COMMENT '端到端耗时（毫秒）',
  `created_at`        DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  -- 拉取历史消息是 WHERE conversation_id = ? ORDER BY created_at，该联合索引同时覆盖过滤与排序
  KEY `idx_conv_created` (`conversation_id`, `created_at`),
  -- ON DELETE CASCADE：删会话即级联删消息，避免应用层漏删产生孤儿数据
  CONSTRAINT `fk_message_conversation`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversation` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';

-- ----------------------------------------------------------------------------
-- retrieval_log：检索可观测日志（可选扩展表）
--   对应 需求分析.md §1.5「可观测性」与 系统设计.md §3.2 的可选扩展表，
--   优先级属「可以有」。表已建好，当前代码尚未写入 —— 保留结构以便后续
--   做「混合检索 vs 纯向量的召回对比」评测时直接落数据。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `retrieval_log` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `message_id`     BIGINT UNSIGNED NOT NULL COMMENT '所属回答',
  `channel`        VARCHAR(16)     NOT NULL COMMENT 'dense | sparse | rerank',
  `query`          VARCHAR(512)    NOT NULL COMMENT '检索用查询串',
  `hit_count`      INT UNSIGNED    NOT NULL COMMENT '命中条数',
  `elapsed_ms`     INT UNSIGNED    NOT NULL COMMENT '该通道耗时',
  `rerank_enabled` TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '是否启用了重排',
  `created_at`     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_message` (`message_id`),
  CONSTRAINT `fk_log_message` FOREIGN KEY (`message_id`)
    REFERENCES `message` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='检索可观测日志';
