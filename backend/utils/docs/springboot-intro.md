# Spring Boot 简介

Spring Boot 是一个基于 Spring 框架的快速开发平台，旨在简化 Spring 应用的创建、配置和部署过程。

## 核心特性

1. 自动配置：Spring Boot 会根据项目依赖自动配置 Spring 应用。
2. 内嵌服务器：支持内嵌 Tomcat、Jetty、Undertow 等服务器，无需单独部署。
3. 启动器依赖：通过 starter POM 简化依赖管理。
4. 生产就绪：提供健康检查、指标监控、外部化配置等功能。

## 快速开始

创建一个 Spring Boot 项目非常简单，只需添加 spring-boot-starter-parent 作为父 POM，然后引入所需的 starter 依赖即可。

```java
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

## 配置文件

Spring Boot 支持 application.properties 和 application.yml 两种配置格式，默认从 classpath 根目录加载。
