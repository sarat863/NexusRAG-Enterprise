import mongoose from 'mongoose';

const CommentSchema = new mongoose.Schema({
  user: { type: String, required: true },
  text: { type: String, required: true },
  time: { type: String, default: 'Just now' },
  createdAt: { type: Date, default: Date.now }
});

const Post = new mongoose.Schema({
  name: { type: String, required: true },
  prompt: { type: String, required: true },
  photo: { type: String, required: true },
  model: { type: String, default: 'Flux.1 Schnell' },
  style: { type: String, default: 'photorealistic' },
  aspectRatio: { type: String, default: '1:1' },
  tags: { type: [String], default: [] },
  likes: { type: Number, default: 0 },
  reactions: {
    fire: { type: Number, default: 0 },
    heart: { type: Number, default: 0 },
    rocket: { type: Number, default: 0 },
    mindblown: { type: Number, default: 0 }
  },
  comments: { type: [CommentSchema], default: [] },
  createdAt: { type: Date, default: Date.now }
});

const PostSchema = mongoose.model('Post', Post);

export default PostSchema;