module.exports = function (api) {
  api.cache(true);
  return {
    presets: [require('expo/node_modules/babel-preset-expo')],
    plugins: [
      [
        'module-resolver',
        {
          root: ['./'],
          alias: {
            '@screens': './src/screens',
            '@stores': './src/stores',
            '@domain': './src/domain',
            '@infrastructure': './src/infrastructure',
            '@shared': './src/shared',
            '@navigation': './src/navigation',
          },
        },
      ],
    ],
  };
};
