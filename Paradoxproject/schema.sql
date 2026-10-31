-- =====================================================================
-- VERITAS AI Database Schema
-- Database: paradox_db
-- Engine: InnoDB
-- Charset: utf8mb4
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `paradox_db`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `paradox_db`;

-- ---------------------------------------------------------------------
-- 1. conversations
-- Stores user sessions across Research and Fact Verification modes
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `conversations` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `mode` ENUM('research', 'fact_check') NOT NULL DEFAULT 'research',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_conversations_mode` (`mode`),
    INDEX `idx_conversations_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. messages
-- Stores chat history linked to a specific conversation
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `messages` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` BIGINT NOT NULL,
    `role` ENUM('user', 'assistant') NOT NULL,
    `content` LONGTEXT NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_messages_conversation_id` (`conversation_id`),
    INDEX `idx_messages_created_at` (`created_at`),
    CONSTRAINT `fk_messages_conversation`
        FOREIGN KEY (`conversation_id`)
        REFERENCES `conversations` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. claims
-- Stores discrete factual claims extracted by AI from assistant responses
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `claims` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `message_id` BIGINT NOT NULL,
    `claim_text` TEXT NOT NULL,
    `verdict` ENUM('supported', 'contradicted', 'unverified') NOT NULL DEFAULT 'unverified',
    `confidence` DECIMAL(5,2) NULL,
    `explanation` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_claims_message_id` (`message_id`),
    INDEX `idx_claims_verdict` (`verdict`),
    CONSTRAINT `fk_claims_message`
        FOREIGN KEY (`message_id`)
        REFERENCES `messages` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4. evidence
-- Stores retrieved web sources and citations corroborating or disputing claims
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `evidence` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `claim_id` BIGINT NOT NULL,
    `source_title` VARCHAR(500) NULL,
    `source_url` VARCHAR(2048) NULL,
    `evidence_snippet` TEXT NULL,
    `evidence_stance` ENUM('supports', 'contradicts', 'context') NOT NULL DEFAULT 'context',
    `retrieved_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_evidence_claim_id` (`claim_id`),
    INDEX `idx_evidence_stance` (`evidence_stance`),
    CONSTRAINT `fk_evidence_claim`
        FOREIGN KEY (`claim_id`)
        REFERENCES `claims` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
