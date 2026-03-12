use actix_web::{web, App, HttpServer, HttpResponse};
use deadpool_postgres::{Config, ManagerConfig, RecyclingMethod, Pool, Runtime};
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio_postgres::NoTls;

#[derive(Serialize)]
struct WorldRow {
    id: i32,
    #[serde(rename = "randomNumber")]
    random_number: i32,
}

#[derive(Serialize)]
struct JsonMessage {
    message: String,
}

struct AppState {
    pool: Pool,
}

async fn plaintext() -> HttpResponse {
    HttpResponse::Ok()
        .content_type("text/plain")
        .body("Hello, World!")
}

async fn json_test() -> HttpResponse {
    HttpResponse::Ok().json(JsonMessage {
        message: "Hello, World!".to_string(),
    })
}

async fn user_by_id(path: web::Path<String>) -> HttpResponse {
    let id = path.into_inner();
    let mut map = HashMap::new();
    map.insert("id", id);
    HttpResponse::Ok().json(map)
}

async fn db_single(data: web::Data<AppState>) -> HttpResponse {
    let client = data.pool.get().await.unwrap();
    let id: i32 = rand::thread_rng().gen_range(1..=10000);
    let row = client
        .query_one("SELECT id, randomnumber FROM world WHERE id = $1", &[&id])
        .await
        .unwrap();
    HttpResponse::Ok().json(WorldRow {
        id: row.get(0),
        random_number: row.get(1),
    })
}

#[derive(Deserialize)]
struct QueryParams {
    count: Option<i32>,
}

async fn db_multi(data: web::Data<AppState>, query: web::Query<QueryParams>) -> HttpResponse {
    let count = query.count.unwrap_or(1).max(1).min(500);
    let client = data.pool.get().await.unwrap();
    let mut results = Vec::with_capacity(count as usize);
    for _ in 0..count {
        let id: i32 = rand::thread_rng().gen_range(1..=10000);
        let row = client
            .query_one("SELECT id, randomnumber FROM world WHERE id = $1", &[&id])
            .await
            .unwrap();
        results.push(WorldRow {
            id: row.get(0),
            random_number: row.get(1),
        });
    }
    HttpResponse::Ok().json(results)
}

async fn template_test(data: web::Data<AppState>) -> HttpResponse {
    let client = data.pool.get().await.unwrap();
    let mut items = Vec::with_capacity(10);
    for _ in 0..10 {
        let id: i32 = rand::thread_rng().gen_range(1..=10000);
        let row = client
            .query_one("SELECT id, randomnumber FROM world WHERE id = $1", &[&id])
            .await
            .unwrap();
        items.push(WorldRow {
            id: row.get(0),
            random_number: row.get(1),
        });
    }
    let rows: String = items
        .iter()
        .map(|w| format!("<tr><td>{}</td><td>{}</td></tr>", w.id, w.random_number))
        .collect();
    let html = format!(
        r#"<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>World Database</h1><table><tr><th>ID</th><th>Random Number</th></tr>{}</table></body></html>"#,
        rows
    );
    HttpResponse::Ok()
        .content_type("text/html; charset=utf-8")
        .body(html)
}

async fn json_body(body: web::Json<serde_json::Value>) -> HttpResponse {
    HttpResponse::Ok().json(body.into_inner())
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let db_url = std::env::var("DATABASE_URL").unwrap_or_else(|_| {
        "host=172.19.0.3 port=5432 user=ntnt password=rQmS9BOUr_yEuc6jZV03bdekIPLxgnou dbname=benchmarks".to_string()
    });

    let mut cfg = Config::new();
    cfg.url = Some(db_url);
    cfg.manager = Some(ManagerConfig {
        recycling_method: RecyclingMethod::Fast,
    });
    let pool = cfg.create_pool(Some(Runtime::Tokio1), NoTls).unwrap();

    // Test connection
    let _client = pool.get().await.expect("Failed to connect to database");
    eprintln!("Database connected, starting server on :3105");

    let data = web::Data::new(AppState { pool });

    HttpServer::new(move || {
        App::new()
            .app_data(data.clone())
            .route("/plaintext", web::get().to(plaintext))
            .route("/json", web::get().to(json_test))
            .route("/users/{id}", web::get().to(user_by_id))
            .route("/db", web::get().to(db_single))
            .route("/queries", web::get().to(db_multi))
            .route("/template", web::get().to(template_test))
            .route("/json", web::post().to(json_body))
    })
    .workers(num_cpus::get())
    .bind("0.0.0.0:3105")?
    .run()
    .await
}
