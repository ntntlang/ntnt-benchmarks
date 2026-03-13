class BenchController < ActionController::API
  def plaintext
    render plain: 'Hello, World!'
  end

  def json_test
    render json: { message: 'Hello, World!' }
  end

  def user_by_id
    render json: { id: params[:id] }
  end

  def db_single
    id = rand(1..10000)
    row = ActiveRecord::Base.connection.select_one(
      "SELECT id, randomnumber FROM world WHERE id = #{ActiveRecord::Base.connection.quote(id)}"
    )
    render json: { id: row['id'], randomNumber: row['randomnumber'] }
  end

  def queries
    count = [[params.fetch(:count, 1).to_i, 1].max, 500].min
    results = count.times.map do
      id = rand(1..10000)
      row = ActiveRecord::Base.connection.select_one(
        "SELECT id, randomnumber FROM world WHERE id = #{ActiveRecord::Base.connection.quote(id)}"
      )
      { id: row['id'], randomNumber: row['randomnumber'] }
    end
    render json: results
  end

  def template_test
    items = 10.times.map do
      id = rand(1..10000)
      ActiveRecord::Base.connection.select_one(
        "SELECT id, randomnumber FROM world WHERE id = #{ActiveRecord::Base.connection.quote(id)}"
      )
    end
    rows = items.map { |i| "<tr><td>#{i['id']}</td><td>#{i['randomnumber']}</td></tr>" }.join
    html = "<!DOCTYPE html><html><head><title>Benchmark</title></head><body>" \
           "<h1>World Database</h1><table><tr><th>ID</th><th>Random Number</th></tr>" \
           "#{rows}</table></body></html>"
    render html: html.html_safe
  end

  def json_body
    render json: JSON.parse(request.body.read)
  end
end
