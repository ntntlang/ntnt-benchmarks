package main

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

var pool *pgxpool.Pool

type World struct {
	ID           int `json:"id"`
	RandomNumber int `json:"randomNumber"`
}

func main() {
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgresql://ntnt:rQmS9BOUr_yEuc6jZV03bdekIPLxgnou@172.19.0.3:5432/benchmarks"
	}

	var err error
	config, _ := pgxpool.ParseConfig(dbURL)
	config.MaxConns = 50
	config.MinConns = 10
	pool, err = pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Unable to connect to database: %v\n", err)
		os.Exit(1)
	}
	defer pool.Close()

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()

	r.GET("/plaintext", func(c *gin.Context) {
		c.String(http.StatusOK, "Hello, World!")
	})

	r.GET("/json", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "Hello, World!"})
	})

	r.GET("/users/:id", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"id": c.Param("id")})
	})

	r.GET("/db", func(c *gin.Context) {
		id := rand.Intn(10000) + 1
		var w World
		err := pool.QueryRow(context.Background(),
			"SELECT id, randomnumber FROM world WHERE id = $1", id).Scan(&w.ID, &w.RandomNumber)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, w)
	})

	r.GET("/queries", func(c *gin.Context) {
		count, _ := strconv.Atoi(c.DefaultQuery("count", "1"))
		if count < 1 {
			count = 1
		}
		if count > 500 {
			count = 500
		}
		results := make([]World, 0, count)
		for i := 0; i < count; i++ {
			id := rand.Intn(10000) + 1
			var w World
			err := pool.QueryRow(context.Background(),
				"SELECT id, randomnumber FROM world WHERE id = $1", id).Scan(&w.ID, &w.RandomNumber)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			results = append(results, w)
		}
		c.JSON(http.StatusOK, results)
	})

	r.GET("/template", func(c *gin.Context) {
		items := make([]World, 0, 10)
		for i := 0; i < 10; i++ {
			id := rand.Intn(10000) + 1
			var w World
			pool.QueryRow(context.Background(),
				"SELECT id, randomnumber FROM world WHERE id = $1", id).Scan(&w.ID, &w.RandomNumber)
			items = append(items, w)
		}
		var sb strings.Builder
		sb.WriteString(`<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>World Database</h1><table><tr><th>ID</th><th>Random Number</th></tr>`)
		for _, item := range items {
			fmt.Fprintf(&sb, "<tr><td>%d</td><td>%d</td></tr>", item.ID, item.RandomNumber)
		}
		sb.WriteString(`</table></body></html>`)
		c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(sb.String()))
	})

	r.POST("/json", func(c *gin.Context) {
		var body interface{}
		if err := c.ShouldBindJSON(&body); err != nil {
			c.JSON(400, gin.H{"error": "invalid json"})
			return
		}
		c.JSON(http.StatusOK, body)
	})

	r.Run(":3103")
}
