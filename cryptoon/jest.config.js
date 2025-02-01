// jest.config.js
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  dir: './',
})

const customJestConfig = {
  setupFiles: ['<rootDir>/.env.test'], // Carrega o arquivo .env.test
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  
}

module.exports = createJestConfig(customJestConfig)