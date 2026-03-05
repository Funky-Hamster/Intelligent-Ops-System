stage('Failure Handler') {
  when { expression { currentBuild.result == 'FAILURE' } }
  steps {
    script {
      def faultType = "disk full" // 实际中需从日志解析
      sh """
        curl -X POST http://ai-om-agent:8001/handle_failure \
        -d '{\"fault_type\": \"$faultType\", \"job_id\": \"$BUILD_ID\"}'
      """
    }
  }
}