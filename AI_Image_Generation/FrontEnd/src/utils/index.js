import FileSaver from 'file-saver';

import { surpriseMePrompts } from '../constants';

export function getRandomPrompt(prompt) {
    const randomIndex = Math.floor(Math.random() * surpriseMePrompts.length);
    const randomPrompt = surpriseMePrompts[randomIndex];

    if(randomPrompt === prompt) return getRandomPrompt(prompt);

    return randomPrompt
}

export async function downloadImage(_id, photo){
    const securePhoto = photo.replace('http://', 'https://');
    FileSaver.saveAs(securePhoto, `download-${_id}.jpg`);
} 