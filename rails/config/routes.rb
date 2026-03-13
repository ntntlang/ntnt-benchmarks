Rails.application.routes.draw do
  get 'plaintext', to: 'bench#plaintext'
  get 'json', to: 'bench#json_test'
  get 'users/:id', to: 'bench#user_by_id'
  get 'db', to: 'bench#db_single'
  get 'queries', to: 'bench#queries'
  get 'template', to: 'bench#template_test'
  post 'json', to: 'bench#json_body'
end
